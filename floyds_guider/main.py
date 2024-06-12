import matplotlib

matplotlib.use('Agg')

import lcogt_logging
import argparse
import datetime
import logging
import os
from floyds_guider import utils, plot
from astropy.io import fits
import tarfile
import jinja2
import shutil
import pkg_resources
import traceback
import sys

logger = logging.getLogger('floyds-guider-frames')

DATA_ROOT = os.path.join(os.path.sep, 'mnt', 'data', 'daydirs')
IMAGE_ROOT_DIRECTORY = os.path.join(os.path.sep, 'var', 'www', 'html', 'images')
SUMMARY_ROOT_DIRECTORY = os.path.join(os.path.sep, 'var', 'www', 'html', 'night_summary')

GUIDER_CAMERAS = {'ogg': 'sd02', 'coj': 'kb32'}
FLOYDS_CAMERAS = {'ogg': 'en06', 'coj': 'en12'}

JINJA_ENVIRONMENT = jinja2.Environment(loader=jinja2.PackageLoader('floyds_guider', 'templates'),
                                       autoescape=jinja2.select_autoescape(['html', 'xml']))


def setup_logging(log_level):
    logger.setLevel(log_level)
    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    handler.setFormatter(lcogt_logging.LCOGTFormatter())
    logger.addHandler(handler)


def get_acquisition_and_first_guiding_images(floyds_frames, guider_frames, output_directory):
    molecules = set(utils.read_keywords_from_fits_files(floyds_frames, 'MOLUID'))

    molecule_frames = []
    for molecule in molecules:
        guider_frames_in_molecule = utils.get_guider_frames_in_molecule(guider_frames, molecule)
        first_acquistion_frame = utils.get_first_acquisition_frame(guider_frames_in_molecule)
        first_guiding_frame = utils.get_first_guiding_frame(guider_frames_in_molecule)
        if first_acquistion_frame is not None and first_guiding_frame is not None:
            acquisition_jpg = utils.convert_raw_fits_path_to_jpg(first_acquistion_frame)
            shutil.copy(acquisition_jpg, os.path.join(output_directory, os.path.basename(acquisition_jpg)))
            guiding_jpg = utils.convert_raw_fits_path_to_jpg(first_guiding_frame)
            shutil.copy(guiding_jpg, os.path.join(output_directory, os.path.basename(guiding_jpg)))
            molecule_frames.append({'id': molecule,
                                    'acquisition_image': os.path.basename(acquisition_jpg),
                                    'first_guiding_image': os.path.basename(guiding_jpg)})
    molecule_frames.sort(key=lambda element: element['id'])
    return molecule_frames


def make_summary_plots(floyds_frames, guider_frames, output_directory):
    summary_plots = []
    # Per science exposure, make guide summary plots

    for science_exposure in utils.get_science_exposures(floyds_frames):
        exposure_basename = os.path.basename(science_exposure).replace('.fits', '')
        ut_start = utils.to_datetime(fits.getval(science_exposure, 'DATE-OBS'))
        ut_stop = ut_start + datetime.timedelta(seconds=fits.getval(science_exposure, 'EXPTIME'))
        guider_frames_for_science_frame = utils.get_guider_frames_for_science_exposure(guider_frames, ut_start, ut_stop)
        plot_set = plot.make_guide_info_plots(guider_frames_for_science_frame, ut_start,
                                              os.path.join(output_directory, exposure_basename))
        for plot_file in plot_set:
            plot_set[plot_file] = os.path.basename(plot_set[plot_file])
        plot_set['science_frame_name'] = os.path.basename(science_exposure)
        summary_plots.append(plot_set)
    summary_plots.sort(key=lambda element: element['science_frame_name'])
    return summary_plots


def make_tar_file_of_guider_frames(guider_frames, summary_plots, summary_output_directory, tar_output_file):
    with tarfile.open(os.path.join(summary_output_directory, tar_output_file), 'w') as tar_file_handle:
        for frame in guider_frames:
            fpacked_file_path = frame.replace('flash', 'raw').replace('g01.fits', 'g00.fits.fz')
            tar_file_handle.add(fpacked_file_path, arcname=os.path.basename(fpacked_file_path))
        for summary_plot in summary_plots:
            for _, plot_file_path in summary_plot.items():
                if '.png' in plot_file_path:
                    tar_file_handle.add(os.path.join(summary_output_directory, plot_file_path),
                                        arcname=os.path.basename(plot_file_path))


def make_guider_summary_webpage(summary_root_name, output_directory, molecule_info, summary_plots, floyds_frames):
    template = JINJA_ENVIRONMENT.get_template('guider_summary_template.html')
    template_css = pkg_resources.resource_filename('floyds_guider', os.path.join('templates', 'styles.css'))
    with open(template_css) as css_file:
        css_style = css_file.read()
    jpgs = [utils.convert_raw_fits_path_to_jpg(frame) for frame in floyds_frames]
    for jpg_file in jpgs:
        shutil.copy(jpg_file, os.path.join(output_directory, os.path.basename(jpg_file)))
    with open(os.path.join(output_directory, summary_root_name + '.html'), 'w') as file_handle:
        file_handle.write(template.render(style_string=css_style, molecules=molecule_info, summary_plots=summary_plots,
                                          floyds_frames=[os.path.basename(jpg_file) for jpg_file in jpgs],
                                          block_title=summary_root_name))


def link_frames_to_images_directory(frames, image_directory):
    if not os.path.exists(image_directory):
        os.mkdir(image_directory)
    for frame in frames:
        try:
            os.symlink(frame, os.path.join(image_directory, os.path.basename(frame)))
        except Exception as e:
            logger.error('Could not link {frame}: {exception}'.format(frame=frame, exception=e))
        # Also copy over the corresponding jpg file
        try:
            jpg_file = frame.replace('flash', 'flash' + os.path.sep + 'jpg').replace('.fits', '.jpg')
            os.symlink(jpg_file, os.path.join(image_directory, os.path.basename(jpg_file)))
        except Exception as e:
            logger.error('Could not link {frame}: {exception}'.format(frame=jpg_file, exception=e))


def process_block(floyds_frames, guider_frames, observation_block, object_name, output_directory):
    floyds_frames_for_block = utils.get_frames_in_block(floyds_frames, observation_block, object_name)
    guider_frames_for_block = utils.get_frames_in_block(guider_frames, observation_block, object_name)

    proposal_id = utils.get_proposal_id(floyds_frames_for_block)
    summary_block_root_name = '_'.join([utils.convert_to_safe_filename(proposal_id),
                                        utils.convert_to_safe_filename(observation_block),
                                        utils.convert_to_safe_filename(object_name)])
    path_for_summary_for_block = os.path.join(output_directory, summary_block_root_name)
    if not os.path.exists(path_for_summary_for_block):
        os.mkdir(path_for_summary_for_block)

    acquisition_and_first_guiding_frames = get_acquisition_and_first_guiding_images(floyds_frames_for_block,
                                                                                    guider_frames_for_block,
                                                                                    path_for_summary_for_block)

    summary_plots = make_summary_plots(floyds_frames_for_block, guider_frames_for_block, path_for_summary_for_block)

    make_guider_summary_webpage(summary_block_root_name, path_for_summary_for_block,
                                acquisition_and_first_guiding_frames, summary_plots, floyds_frames_for_block)
    make_tar_file_of_guider_frames(guider_frames_for_block, summary_plots, path_for_summary_for_block,
                                   summary_block_root_name + '.tar')


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

    floyds_camera = FLOYDS_CAMERAS[args.site]
    guider_camera = GUIDER_CAMERAS[args.site]

    guider_frames = utils.get_files(os.path.join(DATA_ROOT, guider_camera, args.day_obs, 'flash', '*g01.fits'))

    floyds_frames = utils.get_files(os.path.join(DATA_ROOT, floyds_camera, args.day_obs, 'flash', '*01.fits'))

    link_frames_to_images_directory(guider_frames + floyds_frames, os.path.join(IMAGE_ROOT_DIRECTORY, args.day_obs))

    directory_for_summary_on_dayobs = os.path.join(SUMMARY_ROOT_DIRECTORY, args.day_obs)
    if not os.path.exists(directory_for_summary_on_dayobs):
        os.mkdir(directory_for_summary_on_dayobs)

    observation_blocks = utils.read_keywords_from_fits_files(floyds_frames, 'BLKUID')
    objects = utils.read_keywords_from_fits_files(floyds_frames, 'OBJECT')
    for obj, observation_block in set(zip(objects, observation_blocks)):
        try:
            process_block(floyds_frames, guider_frames, observation_block, obj, directory_for_summary_on_dayobs)
        except Exception:
            exc_type, exc_value, exc_tb = sys.exc_info()
            exception_message = traceback.format_exception(exc_type, exc_value, exc_tb)
            logger.error(f'Exception produced for Target: {obj } + Block ID: {observation_block}: {exception_message}')
