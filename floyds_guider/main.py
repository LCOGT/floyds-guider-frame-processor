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

logger = logging.getLogger('floyds-guider-frames')

DATA_ROOT = os.path.join(os.path.sep, 'mnt', 'data', 'daydirs')
IMAGE_ROOT_DIRECTORY = os.path.join(os.path.sep, 'var', 'www', 'html', 'images')
SUMMARY_ROOT_DIRECTORY = os.path.join(os.path.sep, 'var', 'www', 'html', 'night_summary')

GUIDER_CAMERAS = {'ogg': 'kb42', 'coj': 'kb38'}
FLOYDS_CAMERAS = {'ogg': 'en06', 'coj': 'en05'}

JINJA_ENVIRONMENT = jinja2.Environment(loader=jinja2.PackageLoader('floyds_guider', 'templates'),
                                       autoescape=jinja2.select_autoescape(['html', 'xml']))


def setup_logging(log_level):
    logger.setLevel(log_level)
    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    handler.setFormatter(lcogt_logging.LCOGTFormatter())
    logger.addHandler(handler)


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
        plot_set['science_frame_name'] = science_exposure
        summary_plots.append(plot_set)
    summary_plots.sort(key=lambda element: element['science_frame_name'])
    return summary_plots


def make_tar_file_of_guider_frames(guider_frames, summary_plots, tar_output_file):
    with tarfile.open(tar_output_file, 'w') as tar_file_handle:
        for frame in guider_frames:
            fpacked_file_path = frame.replace('flash', 'raw').replace('g01.fits', 'g00.fits.fz')
            tar_file_handle.addfile(tarfile.TarInfo(os.path.basename(fpacked_file_path)), fpacked_file_path)
        for summary_plot in summary_plots:
            for _, plot_file in summary_plot.items():
                if '.png' in plot_file:
                    tar_file_handle.addfile(tarfile.TarInfo(os.path.basename(plot_file)), plot_file)


def make_guider_summary_webpage(output_path, molecule_info, summary_plots, floyds_frames):
    template = JINJA_ENVIRONMENT.get_template('guider_summary_template.html')
    with open(output_path, 'w') as file_handle:
        file_handle.write(template.render(molecules=molecule_info, summary_plots=summary_plots,
                                          floyds_frames=floyds_frames))


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
    for observation_block in set(observation_blocks):

        floyds_frames_for_block = utils.get_frames_in_block(floyds_frames, observation_block)
        guider_frames_for_block = utils.get_frames_in_block(guider_frames, observation_block)

        proposal_id = utils.get_proposal_id(floyds_frames_for_block)
        summary_block_root_name = '_'.join([utils.convert_to_safe_filename(proposal_id),
                                            utils.convert_to_safe_filename(observation_block)])
        path_for_summary_for_block = os.path.join(directory_for_summary_on_dayobs, summary_block_root_name)
        if not os.path.exists(path_for_summary_for_block):
            os.mkdir(path_for_summary_for_block)

        acquisition_and_first_guiding_frames = utils.get_acquisition_and_first_guiding_images(floyds_frames_for_block,
                                                                                              guider_frames_for_block)

        summary_plots = make_summary_plots(floyds_frames_for_block, guider_frames_for_block, path_for_summary_for_block)

        make_guider_summary_webpage(os.path.join(path_for_summary_for_block, summary_block_root_name + '.html'),
                                    acquisition_and_first_guiding_frames, summary_plots, floyds_frames_for_block)
        make_tar_file_of_guider_frames(guider_frames_for_block, summary_plots,
                                       os.path.join(path_for_summary_for_block, summary_block_root_name + '.tar'))
