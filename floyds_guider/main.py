import matplotlib

matplotlib.use('Agg')

import lcogt_logging
import argparse
import datetime
import logging
import os
from floyds_guider import utils
from astropy.io import fits
import tarfile
import jinja2
import shutil

logger = logging.getLogger('floyds-guider-frames')

DATA_ROOT = ''
SUMMARY_ROOT_DIRECTORY = ''

JINJA_ENVIRONMENT = jinja2.Environment(loader=jinja2.PackageLoader('floyds_guider', 'templates'),
                                       autoescape=jinja2.select_autoescape(['html', 'xml']))

GUIDER_CAMERAS = {'ogg': 'kb42', 'coj': 'kb38'}
FLOYDS_CAMERAS = {'ogg': 'en06', 'coj': 'en05'}


def setup_logging(log_level):
    logger.setLevel(log_level)
    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    handler.setFormatter(lcogt_logging.LCOGTFormatter())
    logger.addHandler(handler)

def process_acquisition_and_first_guiding_images(floyds_frames_for_block, guider_frames_for_block, output_directory):
    molecules = set(utils.read_keywords_from_frames(floyds_frames_for_block, 'MOLUID'))

    molecule_frames = []
    for molecule in molecules:
        guider_frames_in_molecule = utils.get_guider_frames_in_molecule(guider_frames_for_block, molecule)
        first_acquistion_frame = utils.get_first_acquisition_frame(guider_frames_in_molecule)
        first_guiding_frame = utils.get_first_guiding_frame(guider_frames_in_molecule)

        if first_acquistion_frame is not None and first_guiding_frame is not None:
            acquisition_jpg_path = os.path.join(output_directory, utils.get_jpeg_filename_from_frame(first_acquistion_frame))
            guiding_jpg_path = os.path.join(output_directory, utils.get_jpeg_filename_from_frame(first_guiding_frame))
            utils.convert_frame_to_jpeg(first_acquistion_frame, acquisition_jpg_path)
            utils.convert_frame_to_jpeg(first_guiding_frame, guiding_jpg_path)
            molecule_frames.append({'id': molecule,
                                    'acquisition_image': os.path.basename(acquisition_jpg_path),
                                    'first_guiding_image': os.path.basename(guiding_jpg_path)})
    molecule_frames.sort(key=lambda element: element['id'])
    return molecule_frames

def process_guide_animations_for_block(floyds_frames_for_block, guider_frames_for_block, output_directory, width, height, fps):
    frames_guiding = utils.get_non_acquisition_guider_frames(guider_frames_for_block)

    guide_animations = []
    for frame in floyds_frames_for_block:
        moluid = utils.read_keywords_from_frames(frame, 'MOLUID')
        ut_start = utils.to_datetime(utils.read_keywords_from_frames(frame, 'DATE-OBS'))
        ut_stop = ut_start + datetime.timedelta(seconds=utils.read_keywords_from_frames(frame, 'EXPTIME'))
        frames_to_animate = utils.get_guider_frames_for_science_exposure(frames_guiding,
                                                                         ut_start,
                                                                         ut_stop)
        #don't create blank animations
        if len(frames_to_animate) == 0:
            continue

        block_id = utils.read_keywords_from_frames(frame, 'BLKUID')
        #TODO: make this something sensible
        output_path = os.path.join(output_directory, moluid + '_' + ut_start.strftime("%X"))
        utils.create_animation_from_frames(frames_to_animate,
                                           output_path,
                                           width=width,
                                           height=height,
                                           fps=fps)
        guide_animations.append(os.path.basename(output_path) + '.gif')

    return guide_animations

def process_science_images_for_block(floyds_frames_for_block, output_directory, width, height):

    science_images = []
    for frame in floyds_frames_for_block:
        science_frame_path = os.path.join(output_directory, utils.get_jpeg_filename_from_frame(frame))
        utils.convert_frame_to_jpeg(frame, science_frame_path, width, height)
        science_images.append(os.path.basename(science_frame_path))

    return science_images

def make_tar_file_of_guider_frames(guider_frames, summary_plot_paths, summary_output_directory, tar_output_file):
    with tarfile.open(os.path.join(summary_output_directory, tar_output_file), 'w') as tar_file_handle:
        for frame in guider_frames:
            fpacked_file_name = utils.get_fpacked_filename_from_frame(frame)
            fpacked_file_path = guider_frame_archive_path + fpacked_file_name
            tar_file_handle.add(fpacked_file_path, arcname=fpacked_file_name)
        for summary_plot in summary_plot_paths:
            for _, plot_file_path in summary_plot.items():
                if '.png' in plot_file_path:
                    tar_file_handle.add(os.path.join(summary_output_directory, plot_file_path),
                                        arcname=os.path.basename(plot_file_path))

def make_guider_summary_webpage(summary_root_name, output_directory, molecule_info, summary_plots, floyds_images, guider_animations):

    template = JINJA_ENVIRONMENT.get_template('guider_summary_template.html')
    with open(os.path.join(output_directory, summary_root_name + '.html'), 'w') as file_handle:
        file_handle.write(template.render(molecules=molecule_info, summary_plots=summary_plots,
                                          floyds_frames=[image for image in floyds_images],
                                          guider_animations = [os.path.basename(animation) for animation in guider_animations],
                                          block_title=summary_root_name))

def process_block(floyds_frames, guider_frames, observation_block, output_directory):

    floyds_frames_for_block = utils.get_frames_in_block(floyds_frames, observation_block)
    guider_frames_for_block = utils.get_frames_in_block(guider_frames, observation_block)

    proposal_id = utils.get_proposal_id(floyds_frames_for_block)
    summary_block_root_name = '_'.join([utils.convert_to_safe_filename(proposal_id),
                                        utils.convert_to_safe_filename(observation_block)])
    path_for_summary_for_block = os.path.join(output_directory, summary_block_root_name)
    if not os.path.exists(path_for_summary_for_block):
        os.mkdir(path_for_summary_for_block)

    acquisition_and_first_guiding_images = process_acquisition_and_first_guiding_images(floyds_frames_for_block,
                                                                                        guider_frames_for_block,
                                                                                        path_for_summary_for_block)
    guider_animations = process_guide_animations_for_block(floyds_frames_for_block,
                                                           guider_frames_for_block,
                                                           path_for_summary_for_block,
                                                           width = 500,
                                                           height = 500,
                                                           fps = 10)

    science_images = process_science_images_for_block(floyds_frames_for_block,
                                                      path_for_summary_for_block,
                                                      width = 500,
                                                      height = 500)

    summary_plots = []

    make_guider_summary_webpage(summary_block_root_name, path_for_summary_for_block,
                                acquisition_and_first_guiding_images, summary_plots,
                                science_images, guider_animations)


def process_guider_frames():
    parser = argparse.ArgumentParser(description='Make summaries of a night of FLOYDS observations and make a '
                                                 'tar file with all of the guider frames during an exposure')
    parser.add_argument('--site', dest='site', required=True, help='Site code', choices=['ogg', 'coj'])
    parser.add_argument('--day-obs', dest='day_obs', default=None, help='DAY-OBS to summarize')
    parser.add_argument('--log-level', dest='log_level', default='INFO', help='Logging level',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    args = parser.parse_args()
    setup_logging(getattr(logging, args.log_level))

    if args.day_obs is None:
        args.day_obs = utils.get_default_dayobs(args.site)

    logger.info('Processing FLOYDS guider frames for {site} on {dayobs}'.format(site=args.site, dayobs=args.day_obs))

    floyds_camera = utils.get_camera_codes("http://configdb.lco.gtn/cameras/", 4)[args.site]
    guider_camera = utils.get_camera_codes("http://configdb.lco.gtn/cameras/", 13)[args.site]

    guider_frames = utils.get_good_frames_from_path(DATA_ROOT + utils.get_path(args.site, guider_camera, args.day_obs))
    floyds_frames = utils.get_good_frames_from_path(DATA_ROOT + utils.get_path(args.site, floyds_camera, args.day_obs))

    if (len(floyds_frames) == 0):
        raise FileNotFoundError("Test data path: {test_data_path}".format(test_data_path = DATA_ROOT + utils.get_path(args.site, floyds_camera, args.day_obs)))

    directory_for_summary_on_dayobs = os.path.join(SUMMARY_ROOT_DIRECTORY, args.day_obs)
    if not os.path.exists(directory_for_summary_on_dayobs):
        os.mkdir(directory_for_summary_on_dayobs)

    observation_blocks = utils.read_keywords_from_frames(floyds_frames, 'BLKUID')
    for observation_block in set(observation_blocks):
        try:
            process_block(floyds_frames, guider_frames, observation_block, directory_for_summary_on_dayobs)
        except Exception as e:
            logger.error('Exception produced for Block ID: {block}: {exception}'.format(block=observation_block,
                                                                                        exception=e))
