from os.path import join
from absl import app, flags
import numpy as np
from tqdm import tqdm
import cv2

from third_party.xiuminglib import xiuminglib as xm
from data_gen.util import gen_data


flags.DEFINE_string('cam_dir', '', "")
flags.DEFINE_string('img_root', '', "")
flags.DEFINE_string('outroot', '', "")
flags.DEFINE_list('scenes', [], "")
flags.DEFINE_integer('h', 256, "")
flags.DEFINE_integer('n_vali', 2, "")
flags.DEFINE_boolean('debug', False, "debug toggle")
flags.DEFINE_boolean('overwrite', False, "overwrite toggle")
FLAGS = flags.FLAGS


def main(_):
    xm.os.makedirs(FLAGS.outroot, rm_if_exists=FLAGS.overwrite)

    for scene in tqdm(FLAGS.scenes, desc="Scenes"):
        # Glob poses
        cam_paths = xm.os.sortglob(FLAGS.cam_dir, filename='pos_???', ext='txt')

        # Glob images
        img_dir = join(FLAGS.img_root, scene)
        ext = 'png'
        img_paths = xm.os.sortglob( # the most diffuse lighting
            img_dir, filename='*_3_*', ext=ext)
        assert img_paths, "No image globbed"

        # In case only the first 49 cameras are used to capture images
        cam_paths = cam_paths[:len(img_paths)]

        if FLAGS.debug:
            img_paths = img_paths[:4]
            cam_paths = cam_paths[:4]

        # Sanity check
        n_poses = len(cam_paths)
        n_imgs = len(img_paths)
        assert n_poses == n_imgs, (
            "Mismatch between numbers of images ({n_imgs}) and "
            "poses ({n_poses})").format(n_imgs=n_imgs, n_poses=n_poses)

        poses, imgs = [], []
        factor = None
        for img_path, cam_path in tqdm(
                zip(img_paths, cam_paths), desc="Converting", total=n_imgs):
            # Load and resize image
            img = xm.io.img.read(img_path)
            img = xm.img.normalize_uint(img)
            if factor is None:
                factor = float(img.shape[0]) / FLAGS.h
            else:
                assert float(img.shape[0]) / FLAGS.h == factor, \
                    "Images are of varying sizes"
            print('B: Resizing image of shape ', img.shape, ' to ', FLAGS.h)  # Zack 11/20 7pm
            img = xm.img.resize(img, new_h=FLAGS.h, method='tf')
            if img.shape[2] == 3:
                # NOTE: add an all-one alpha
                img = np.dstack((img, np.ones_like(img)[:, :, :1]))
            imgs.append(img)

            # Pose
            P = np.loadtxt(cam_path)
            K = cv2.decomposeProjectionMatrix(P)[0]
            Rt = np.linalg.inv(K).dot(P) # w2cvc
            Rt = xm.camera.CVCAM_TO_GLCAM.dot(Rt) # w2glc
            K = K / K[2, 2]
            f = (K[0, 0] + K[1, 1]) / 2 # hacky but need a single focal length
            f *= 1. / factor # scale according to the new resolution
            #
            Rt = np.vstack([Rt, [0, 0, 0, 1]]) # w2glc
            Rt = np.linalg.inv(Rt) # glc2w
            pose = Rt # c2w
            # Camera-to-world (OpenGL)
            hw = np.array(img.shape[:2]).reshape([2, 1])
            hwf = np.vstack((hw, [f]))
            pose = np.hstack((pose[:3, :], hwf))
            poses.append(pose)
        imgs = np.stack(imgs, axis=-1)
        poses = np.dstack(poses) # 3x5xN

        # Move variable dim to axis 0
        poses = np.moveaxis(poses, -1, 0).astype(np.float32) # Nx3x5
        imgs = np.moveaxis(imgs, -1, 0) # NxHxWx4

        outdir = join(FLAGS.outroot, scene)
        gen_data(poses, imgs, img_paths, FLAGS.n_vali, outdir)


if __name__ == '__main__':
    app.run(main=main)
