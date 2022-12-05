# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from os import makedirs
from os.path import join, basename, exists
import numpy as np
from absl import app, flags
from tqdm import tqdm
import tensorflow as tf

from third_party.xiuminglib import xiuminglib as xm
from brdf.renderer import gen_light_xyz
from nerfactor import datasets
from nerfactor import models
from nerfactor.util import io as ioutil, logging as logutil, \
    config as configutil, img as imgutil, geom as geomutil


flags.DEFINE_string(
    'trained_nerf', '',
    "path to trained NeRF up to (and including) learning rate folder")
flags.DEFINE_string('data_root', '', "input data root")
flags.DEFINE_string('out_root', '', "output root")
flags.DEFINE_integer(
    'imh', None, "image height (defaults to what was used for NeRF training)")
flags.DEFINE_string(
    'scene_bbox', None, (
        "format: x_min,x_max,y_min,y_max,z_min,z_max; for bounding real "
        "scenes within a bounding box"))
flags.DEFINE_float('lvis_far', 1, "far plane for tracing light visibility")
flags.DEFINE_float(
    'occu_thres', 0, "occupancy threshold that surface points have to pass")
flags.DEFINE_integer(
    'light_h', 16, "number of pixels along environment map's height (latitude)")
flags.DEFINE_integer(
    'mlp_chunk', 1_500_000, (
        "chunk size for MLP (bump this up until your GPU gets OOM, "
        "for faster computation)"))
flags.DEFINE_integer(
    'lpix_chunk', 1, (
        "number of light probe pixels to be processed in parallel "
        "(doesn't matter much performance-wise)"))
flags.DEFINE_integer('spp', 1, "samples per pixel")
flags.DEFINE_integer(
    'fps', 12, "frames per second for visualizing light visibility")
flags.DEFINE_boolean('debug', False, "whether in debug mode")
FLAGS = flags.FLAGS

logger = logutil.Logger(loggee="geometry_from_nerf")


def main(_):
    # Get the latest checkpoint
    ckpts = xm.os.sortglob(
        join(FLAGS.trained_nerf, 'checkpoints'), 'ckpt-*.index')
    ckpt_ind = [
        int(basename(x)[len('ckpt-'):-len('.index')]) for x in ckpts]
    latest_ckpt = ckpts[np.argmax(ckpt_ind)]
    latest_ckpt = latest_ckpt[:-len('.index')]

    # Load its config.
    config_ini = configutil.get_config_ini(latest_ckpt)
    config = ioutil.read_config(config_ini)
    if FLAGS.imh is not None: # if using a new image resolution
        config.set('DEFAULT', 'imh', str(FLAGS.imh))
    print("Image resolution: ", str(FLAGS.imh))

    # Restore model
    model = restore_model(config, latest_ckpt)

    print("Restored model")

    # Zack: manual parallelization
    startCount =  0
    doThisMany = 25
    count = -1

    for mode in ['test', 'train', 'vali']: # 308
        # Make datapipe
        n_views, datapipe = make_datapipe(config, mode)

        print("Made datapipe for", mode, ", but skipping first", startCount)


        # Process all views of this mode
        for batch in tqdm(datapipe, desc=f"Views ({mode})", total=n_views):

            count = count + 1

            if count < startCount or doThisMany == 0:
                print("Skipping view", count, " (", mode, ")")
                continue

            print("Processing view", count, " (", mode, ")")
            doThisMany = doThisMany - 1;
            process_view(config, model, batch)

            if FLAGS.debug:
                continue


def process_view(config, model, batch):
    sps = int(np.sqrt(FLAGS.spp)) # no need to check if square

    id_, hw, rayo, rayd, _ = batch
    id_ = id_[0].numpy().decode()
    hw = hw[0, :]

    print("Process view", id_)

    rayd = tf.linalg.l2_normalize(rayd, axis=1)

    out_dir = join(FLAGS.out_root, id_)
    if not exists(out_dir):
        makedirs(out_dir)

    # Is this job done already?
    expected = [
        join(out_dir, 'alpha.png'),
        join(out_dir, 'lvis.npy'), join(out_dir, 'lvis.png'),
        join(out_dir, 'normal.npy'), join(out_dir, 'normal.png'),
        join(out_dir, 'xyz.npy'), join(out_dir, 'xyz.png')]
    all_exist = all(exists(x) for x in expected)
    print([exists(x) for x in expected])
    print(all_exist)
    if all_exist:
        logger.info(f"Skipping {id_} since it's done already")
        return

    print("Checked job done")

    # ------ Tracing from Camera to Object

    occu, exp_depth, exp_normal = compute_depth_and_normal(
        model, rayo, rayd, config)
    print("Traced from camera to object")

    # Clip smaller-than-threshold alpha to 0
    transp_ind = tf.where(occu < FLAGS.occu_thres)
    occu = tf.tensor_scatter_nd_update(
        occu, transp_ind, tf.zeros((tf.shape(transp_ind)[0],)))
    print("Clipped alpha")

    # Write alpha map, transparency
    alpha_map = tf.reshape(occu, hw * sps)
    alpha_map = average_supersamples(alpha_map, sps)
    alpha_map = tf.clip_by_value(alpha_map, 0., 1.)
    geomutil.write_alpha(alpha_map, out_dir)
    print("Finish writing alpha map")

    # Write XYZ map, whose background filling value is (0, 0, 0)
    surf = rayo + rayd * exp_depth[:, None] # Surface XYZs
    xyz_map = tf.reshape(surf, (hw[0] * sps, hw[1] * sps, 3))
    xyz_map = average_supersamples(xyz_map, sps)
    xyz_map = imgutil.alpha_blend(xyz_map, alpha_map)
    geomutil.write_xyz(xyz_map, out_dir)
    print("Finish writing xyz map")

    # Write normal map, whose background filling value is (0, 1, 0),
    # since using (0, 0, 0) leads to (0, 0, 0) tangents
    normal_map = tf.reshape(exp_normal, (hw[0] * sps, hw[1] * sps, 3))
    normal_map = average_supersamples(normal_map, sps)
    normal_map_bg = tf.convert_to_tensor((0, 1, 0), dtype=tf.float32)
    normal_map_bg = tf.tile(normal_map_bg[None, None, :], tuple(hw) + (1,))
    normal_map = imgutil.alpha_blend(normal_map, alpha_map, normal_map_bg)
    normal_map = tf.linalg.l2_normalize(normal_map, axis=2)
    normal_map = tf.clip_by_value(normal_map, -1., 1.)
    geomutil.write_normal(normal_map, out_dir)
    print("Finish writing normal map")

    # ------ Tracing from Object to light

    # Don't waste memory on those "miss" rays
    hit = tf.reshape(alpha_map, (-1,)) > 0. # alpha > 0 means occu > occu_thres
    surf = tf.boolean_mask(surf, hit, axis=0)
    normal = tf.boolean_mask(exp_normal, hit, axis=0)

    lvis_hit = compute_light_visibility(
        model, surf, normal, config) # (n_surf_pts, n_lights)
    lvis_hit = np.clip(lvis_hit, 0., 1.)
    n_lights = lvis_hit.shape[1]
    print("Finish computing light vis")

    # Put the light visibility values into the full tensor
    hit_map = hit.numpy().reshape(tuple(hw) + (1,))
    lvis = np.zeros( # (imh, imw, n_lights)
        tuple(hw) + (n_lights,), dtype=np.float32)
    lvis[np.broadcast_to(hit_map, lvis.shape)] = lvis_hit.ravel()
    print("Finish putting alpha map")

    # Mask visibility maps with alpha maps
    for i in range(lvis.shape[2]):
        lvis[:, :, i] = imgutil.alpha_blend(lvis[:, :, i], alpha_map)
    print("Finish making light vis map")

    # Write light visibility map
    geomutil.write_lvis(lvis, FLAGS.fps, out_dir)
    print("Finish writing light vis map")


def compute_light_visibility(model, surf, normal, config, lvis_near=.1):
    n_samples_coarse = 64 + config.getint('DEFAULT', 'n_samples_coarse')
    n_samples_fine = 64 + config.getint('DEFAULT', 'n_samples_fine')
    lin_in_disp = config.getboolean('DEFAULT', 'lin_in_disp')
    perturb = False # NOTE: don't randomize at test time

    light_w = 2 * FLAGS.light_h
    lxyz, lareas = gen_light_xyz(FLAGS.light_h, light_w)
    lxyz = tf.convert_to_tensor(lxyz.astype(np.float32))
    lareas = tf.convert_to_tensor(lareas.astype(np.float32))
    lxyz_flat = tf.reshape(lxyz, (1, -1, 3))

    n_lights = lxyz_flat.shape[1]
    lvis_hit = np.zeros(
        (surf.shape[0], n_lights), dtype=np.float32) # (n_surf_pts, n_lights)
    print("n_lights: ", n_lights)
    for i in range(0, n_lights, FLAGS.lpix_chunk):
        print("LightVis chunk ", i)
        end_i = min(n_lights, i + FLAGS.lpix_chunk)
        lxyz_chunk = lxyz_flat[:, i:end_i, :] # (1, lpix_chunk, 3)
        print(lxyz_chunk)

        # From surface to lights
        surf2l = lxyz_chunk - surf[:, None, :] # (n_surf_pts, lpix_chunk, 3)
        surf2l = tf.math.l2_normalize(surf2l, axis=2)
        surf2l_flat = tf.reshape(surf2l, (-1, 3)) # (n_surf_pts * lpix_chunk, 3)

        surf_rep = tf.tile(surf[:, None, :], (1, surf2l.shape[1], 1))
        surf_flat = tf.reshape(surf_rep, (-1, 3)) # (n_surf_pts * lpix_chunk, 3)

        # Save memory by ignoring back-lit points
        lcos = tf.einsum('ijk,ik->ij', surf2l, normal)
        front_lit = lcos > 0 # (n_surf_pts, lpix_chunk)
        if tf.reduce_sum(tf.cast(front_lit, float)) == 0:
            # If there is no point being front lit, this visibility buffer is
            # zero everywhere, so no need to update this slice
            continue
        front_lit_flat = tf.reshape(
            front_lit, (-1,)) # (n_surf_pts * lpix_chunk)
        surf_flat_frontlit = tf.boolean_mask(surf_flat, front_lit_flat, axis=0)
        surf2l_flat_frontlit = tf.boolean_mask( # (n_frontlit_pairs, 3)
            surf2l_flat, front_lit_flat, axis=0)

        # Query coarse model
        z = model.gen_z( # NOTE: start from lvis_near instead of 0
            lvis_near, FLAGS.lvis_far, n_samples_coarse,
            surf2l_flat_frontlit.shape[0], lin_in_disp=lin_in_disp,
            perturb=perturb)
        pts = surf_flat_frontlit[:, None, :] + \
            surf2l_flat_frontlit[:, None, :] * z[:, :, None]
        pts_flat = tf.reshape(pts, (-1, 3))
        sigma_flat = eval_sigma_mlp(model, pts_flat, use_fine=False)
        sigma = tf.reshape(sigma_flat, pts.shape[:2])
        weights = model.accumulate_sigma(sigma, z, surf2l_flat_frontlit)

        # Obtain additional samples using importance sampling
        z = model.gen_z_fine(z, weights, n_samples_fine, perturb=perturb)
        pts = surf_flat_frontlit[:, None, :] + \
            surf2l_flat_frontlit[:, None, :] * z[:, :, None]
        pts_flat = tf.reshape(pts, (-1, 3))

        # Evaluate all samples with the fine model
        sigma_flat = eval_sigma_mlp(model, pts_flat, use_fine=True)
        sigma = tf.reshape(sigma_flat, pts.shape[:2])
        weights = model.accumulate_sigma(sigma, z, surf2l_flat_frontlit)
        occu = tf.reduce_sum(weights, -1) # (n_frontlit_pairs,)

        # Put the light visibility values into the full tensor
        front_lit_full = np.zeros(lvis_hit.shape, dtype=bool)
        front_lit_full[:, i:end_i] = front_lit.numpy()
        lvis_hit[front_lit_full] = 1 - occu.numpy()

    return lvis_hit # (n_surf_pts, n_lights)


def compute_depth_and_normal(model, rayo, rayd, config):
    n_samples_coarse = 64 + config.getint('DEFAULT', 'n_samples_coarse')
    n_samples_fine = 64 + config.getint('DEFAULT', 'n_samples_fine')
    lin_in_disp = config.getboolean('DEFAULT', 'lin_in_disp')
    perturb = False # NOTE: do not randomize at test time
    near = config.getfloat('DEFAULT', 'near')
    far = config.getfloat('DEFAULT', 'far')

    # Points in space to evaluate the coarse model at
    z = model.gen_z(
        near, far, n_samples_coarse, rayo.shape[0], lin_in_disp=lin_in_disp,
        perturb=perturb)
    pts = rayo[:, None, :] + rayd[:, None, :] * z[:, :, None] # shape is
    # (n_rays, n_samples, 3)
    pts_flat = tf.reshape(pts, (-1, 3))

    # Evaluate coarse model for importance sampling
    sigma_flat = eval_sigma_mlp(model, pts_flat, use_fine=False)
    sigma = tf.reshape(sigma_flat, pts.shape[:2])
    weights = model.accumulate_sigma(sigma, z, rayd)

    # Obtain additional samples using importance sampling
    z = model.gen_z_fine(z, weights, n_samples_fine, perturb=perturb)
    pts = rayo[:, None, :] + rayd[:, None, :] * z[:, :, None]
    pts_flat = tf.reshape(pts, (-1, 3))

    # For real scenes: sigma out of bounds should be 0
    in_bounds = check_bounds(pts_flat)
    out_ind = tf.where(~in_bounds)

    # Evaluate all samples with the fine model
    embedder = model.embedder['xyz']
    fine_enc = model.net['fine_enc']
    fine_sigma_out = model.net.get(
        'fine_a_out', model.net['fine_sigma_out'])
    sigma_chunks, normal_chunks = [], [] # chunk by chunk to avoid OOM
    for i in range(0, pts_flat.shape[0], FLAGS.mlp_chunk):
        print("Depth&Normal chunk ", i)
        end_i = min(pts_flat.shape[0], i + FLAGS.mlp_chunk)
        pts_chunk = pts_flat[i:end_i, :]
        # Sigma
        with tf.GradientTape() as g:
            g.watch(pts_chunk)
            sigma_chunk = tf.nn.relu(
                fine_sigma_out(fine_enc(embedder(pts_chunk))))
        # Normals: derivatives of sigma
        bjac_chunk = g.batch_jacobian(sigma_chunk, pts_chunk)
        bjac_chunk = tf.reshape(
            bjac_chunk, (bjac_chunk.shape[0], 3)) # safe squeezing
        normal_chunk = -tf.linalg.l2_normalize(bjac_chunk, axis=1)
        #
        sigma_chunks.append(sigma_chunk)
        normal_chunks.append(normal_chunk)

    assert sigma_chunks, "No sigma chunk to concat."
    sigma_flat = tf.concat(sigma_chunks, axis=0)
    # Override out-of-bounds sigma to 0
    sigma_flat = tf.tensor_scatter_nd_update(
        sigma_flat, out_ind, tf.zeros((tf.shape(out_ind)[0], 1)))
    assert normal_chunks, "No normal chunk to concat."
    normal_flat = tf.concat(normal_chunks, axis=0)
    sigma = tf.reshape(sigma_flat, pts.shape[:2]) # (n_rays, n_samples)
    normal = tf.reshape(normal_flat, pts.shape) # (n_rays, n_samples, 3)

    # Accumulate samples into expected depth and normals
    weights = model.accumulate_sigma(sigma, z, rayd) # (n_rays, n_samples)
    occu = tf.reduce_sum(weights, -1) # (n_rays,)
    # Estimated depth is expected distance
    exp_depth = tf.reduce_sum(weights * z, axis=-1) # (n_rays,)
    # Computed weighted normal along each ray
    exp_normal = tf.reduce_sum(weights[:, :, None] * normal, axis=-2)

    return occu, exp_depth, exp_normal


def eval_sigma_mlp(model, pts, use_fine=False):
    embedder = model.embedder['xyz']
    if use_fine:
        pref = 'fine_'
    else:
        pref = 'coarse_'
    enc = model.net[pref + 'enc']
    sigma_out = model.net.get(pref + 'a_out', model.net[pref + 'sigma_out'])

    # For real scenes: override out-of-bound sigma to be 0
    in_bounds = check_bounds(pts)
    pts_in = tf.boolean_mask(pts, in_bounds)

    # Chunk by chunk to avoid OOM
    sigma_chunks = []
    for i in range(0, pts_in.shape[0], FLAGS.mlp_chunk):
        end_i = min(pts_in.shape[0], i + FLAGS.mlp_chunk)
        pts_chunk = pts_in[i:end_i, :]
        sigma_chunk = tf.nn.relu(sigma_out(enc(embedder(pts_chunk))))
        sigma_chunks.append(sigma_chunk)
    assert sigma_chunks, "No sigma chunk to concat."
    sigma_in = tf.concat(sigma_chunks, axis=0)

    # Assign these predicted sigma to a full zero tensor
    full_shape = (tf.shape(pts)[0], 1)
    in_ind = tf.where(in_bounds)
    sigma = tf.scatter_nd(in_ind, sigma_in, full_shape)

    return sigma


def average_supersamples(map_supersampled, sps):
    maps = []
    for i in range(sps):
        for j in range(sps):
            sample = map_supersampled[i::sps, j::sps, ...]
            sample = sample[None, ...]
            maps.append(sample)
    assert maps, "No map to concat."
    maps = tf.concat(maps, axis=0)
    return tf.reduce_mean(maps, axis=0)


def check_bounds(pts):
    if FLAGS.scene_bbox is None or FLAGS.scene_bbox == '':
        return tf.ones((tf.shape(pts)[0],), dtype=bool)
    # Parse bounds
    x_min, x_max, y_min, y_max, z_min, z_max = FLAGS.scene_bbox.split(',')
    # Assume cube bottom center at world origin on XY plane
    x_min, x_max = float(x_min), float(x_max)
    y_min, y_max = float(y_min), float(y_max)
    z_min, z_max = float(z_min), float(z_max)
    in_x = tf.logical_and(pts[:, 0] >= x_min, pts[:, 0] <= x_max)
    in_y = tf.logical_and(pts[:, 1] >= y_min, pts[:, 1] <= y_max)
    in_z = tf.logical_and(pts[:, 2] >= z_min, pts[:, 2] <= z_max)
    in_bounds = tf.logical_and(in_x, tf.logical_and(in_y, in_z))
    return in_bounds


def make_datapipe(config, mode):
    dataset_name = config.get('DEFAULT', 'dataset')
    no_batch = config.getboolean('DEFAULT', 'no_batch')
    Dataset = datasets.get_dataset_class(dataset_name)
    dataset = Dataset(config, mode, always_all_rays=True, spp=FLAGS.spp)
    n_views = dataset.get_n_views()
    datapipe = dataset.build_pipeline(no_batch=no_batch, no_shuffle=True)
    return n_views, datapipe


def restore_model(config, ckpt_path):
    model_name = config.get('DEFAULT', 'model')
    Model = models.get_model_class(model_name)
    model = Model(config)
    ioutil.restore_model(model, ckpt_path)
    return model


if __name__ == '__main__':
    app.run(main)
