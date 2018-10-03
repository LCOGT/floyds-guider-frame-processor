import datetime
import os
from glob import glob
from xml.etree import ElementTree
import requests
from pandas import read_table

import requests
from pandas import read_table
import tempfile
from fits2image import conversions
import imageio

import numpy as np
from astropy.io import fits
from astropy.time import Time

import string
import logging

logger = logging.getLogger('floyds-guider-frames')
MINIMUM_GOOD_FILE_SIZE = 100000  # in bytes


def convert_to_safe_filename(unsafe_string):
    valid_filename_characters = "-_.(){letters}{numbers}".format(letters=string.ascii_letters, numbers=string.digits)
    return ''.join(character for character in unsafe_string if character in valid_filename_characters)


def read_keywords_from_fits_files(fits_file_paths, keyword):
    """Loops through the list of FITS frames, reading in
    the fits header keyword and returning this as a list"""
    return [fits.getval(guider_fits_filename, keyword=keyword) for guider_fits_filename in fits_file_paths]


def to_datetime(date_string):
    return Time(date_string).datetime


def in_date_range(date_to_check, start, end):
    taken_after_start = (to_datetime(date_to_check) - to_datetime(start)).total_seconds() > 0
    taken_before_end = (to_datetime(date_to_check) - to_datetime(end)).total_seconds() < 0
    return taken_after_start and taken_before_end


def get_guider_frames_during_exposure(guider_frames, ut_start, ut_stop):
    guider_start_times = read_keywords_from_fits_files(guider_frames, 'DATE-OBS')
    taken_during_exposure = [True if in_date_range(start_time, ut_start, ut_stop) else False
                             for start_time in guider_start_times]
    return [guider_frame for guider_frame, should_use in zip(guider_frames, taken_during_exposure) if should_use]


def get_relative_guider_observation_times(guider_frames, ut_start):
    dates_of_guider_frames = [to_datetime(guider_date)
                              for guider_date in read_keywords_from_fits_files(guider_frames, 'DATE-OBS')]
    guider_exposure_times = read_keywords_from_fits_files(guider_frames, 'EXPTIME')
    return [(guider_frame_date - to_datetime(ut_start)).total_seconds() + guider_exposure_time / 2.0
            for guider_frame_date, guider_exposure_time in zip(dates_of_guider_frames, guider_exposure_times)]


def read_stats_from_xml_files(xml_files):
    stats = {'total_counts': [], 'x_center': [], 'y_center': [], 'fwhm': []}
    for xml_file in xml_files:
        for keyword, value in zip(['total_counts', 'x_center', 'y_center', 'fwhm'],
                                  extract_stats_from_xml_file(xml_file)):
            stats[keyword].append(value)
    return stats


def extract_stats_from_xml_file(xml_file):
    tree = ElementTree.parse(xml_file)
    for centroid in tree.findall('centroids'):
        if centroid.find('guideStar').text == 'true':
            total_counts = float(centroid.find('totalFlux').text)
            x_center = float(centroid.find('pixel').find('x').text)
            y_center = float(centroid.find('pixel').find('y').text)
            fwhm = float(centroid.find('fwhm').text)
            stats = total_counts, x_center, y_center, fwhm
    # Fallback in case there is no guide star in the xml file
    try:
        stats
    except NameError:
        logger.error('No guide star found in {xml_file}'.format(xml_file=xml_file))
        stats = np.nan, np.nan, np.nan, np.nan
    return stats

def get_site_from_camera_code(camera_code):
    """
    Returns a site, given a camera code. Uses LCO camera mapping file
    available at: http://configdb.lco.gtn/camera_mappings/

    :param camera_code: camera code defined in ConfigDB (e.g. kb38)
    :return: LCO site where camera is located
    """
    camera_mapping_url = "http://configdb.lco.gtn/camera_mappings/"
    camera_mappings = read_table(camera_mapping_url, sep='\s+', header=0, escapechar='#')

    site_list = camera_mappings[' Site'].tolist()
    ag_camera_list = camera_mappings['Autoguider'].tolist()
    camera_list = camera_mappings['Camera'].tolist()

    for site, ag_camera, camera in zip(site_list, ag_camera_list, camera_list):
        if (ag_camera == camera_code) or (camera == camera_code):
            return site
    else:
        return None

def get_camera_codes(config_root_url, camera_type):
    """
    Get all camera codes and corresponding sites for a given camera
    type id from ConfigDB

    :param config_root_url: url to configuration database (e.g. http://configdb.lco.gtn/cameras/)
    :param camera_type: ConfigDB camera type id (http://configdb.lco.gtn/cameratypes/)
    :return: dictionary of the form {camera_code : site}
    """
    root_url = "http://configdb.lco.gtn/cameras/"
    parameters = dict(camera_type=str(camera_type))

    response = requests.get(url=root_url, params=parameters).json()
    results = response['results']
    camera_info = {}

    for result in results:
        camera_info[result['code']] = get_site_from_camera_code(result['code'])

    return camera_info

def get_path(site_code, camera_code, observation_date):
    """
    Get path (in glob form) to frames on Chanunpa given site code,
    camera code, and observation date

    :param site_code: LCO 3-letter site code
    :param camera_code: camera code defined in ConfigDB (e.g. kb38)
    :param observation_date: date in YYYYMMDD format
    :return: path to frames on Chanunpa
    """

    base_path = os.path.join("/", "archive", "engineering")
    frames_path = os.path.join(base_path, str(site_code), str(camera_code),
                                     str(observation_date), "raw", "*")
    return frames_path


def get_good_frames_from_path(path):
    """
    Given a directory of fits.fz files, open them and return a list
    of frames
    """
    frames = sorted(glob(path))
    # Reject empty images
    frames = [open_fits_file(frame) for frame in frames if os.path.getsize(frame) > MINIMUM_GOOD_FILE_SIZE]
    return frames

def open_fits_file(filename):
    """
    Opens a fits.fz file and return an hdulist
    """
    base_filename, file_extension = os.path.splitext(os.path.basename(filename))
    if file_extension == '.fz':
        with tempfile.TemporaryDirectory() as tmpdirname:
            output_filename = os.path.join(tmpdirname, base_filename)
            os.system('funpack -O {0} {1}'.format(output_filename, filename))
            hdulist = fits.open(output_filename, 'readonly')
    else:
        hdulist = fits.open(filename, 'readonly')

    return hdulist

def read_keywords_from_hdu_lists(hdu_lists, keyword):
    """
    Retrieves keyword(s) from a single HDUList or a
    list of HDULists
    :param hdu_lists: Single HDUList or list of HDULists
    :param keyword: Header keyword to retrieve
    :return: Single value, or list of values
    """
    if isinstance(hdu_lists, fits.hdu.hdulist.HDUList):
        return hdu_lists[0].header[keyword]

    return [hdu_list[0].header[keyword] for hdu_list in hdu_lists]

def create_animation_from_frames(frames, output_path, fps=10, height=500, width=500):
    """
    Given a set of frames, create a GIF animation.
    """
    writer = imageio.get_writer(output_path + '.gif', fps = fps)

    for frame in frames:
        with tempfile.NamedTemporaryFile() as temp_jpg_file:
            temp_fits_file = tempfile.NamedTemporaryFile()
            frame.writeto(temp_fits_file.name)
            conversions.fits_to_jpg(temp_fits_file.name, temp_jpg_file.name, width=width, height=height)
            writer.append_data(imageio.imread(temp_jpg_file))

    writer.close()
    logger.debug("Finished processing animation.")


def get_default_dayobs(site):
    if 'ogg' in site:
        # Default day-obs is yesterday
        day_obs = datetime.datetime.now() - datetime.timedelta(days=1)
    else:
        day_obs = datetime.datetime.now()
    return day_obs.strftime('%Y%m%d')

def get_tracking_guider_frames(guider_frames):
    """
    Given a set of guide frames, return all that are 'guiding' - e.g.
    locked onto a target.
    """
    guider_states = read_keywords_from_hdu_lists(guider_frames, 'AGSTATE')
    return [frame for state, frame in zip(guider_states, guider_frames) if 'GUIDING' in state]


def get_guider_frames_in_molecule(frames, molecule):
    molecule_ids = read_keywords_from_fits_files(frames, 'MOLUID')
    return [frame for molecule_id, frame in zip(molecule_ids, frames) if molecule_id == molecule]


def get_first_acquisition_frame(guider_frames):
    guider_states = read_keywords_from_hdu_lists(guider_frames, 'AGSTATE')
    acquisition_frames = [frame for state, frame in zip(guider_states, guider_frames) if 'ACQUIRING' in state]
    acquisition_frames.sort(key = lambda frame:frame[0].header['DATE-OBS'])

    return acquisition_frames[0] if len(acquisition_frames) > 0 else None


def get_science_exposures(frames):
    obstypes = read_keywords_from_hdu_lists(frames, 'OBSTYPE')
    return [frame for obstype, frame in zip(obstypes, frames) if obstype == 'SPECTRUM']


def get_frames_in_block(frames, block_id):
    block_ids = read_keywords_from_hdu_lists(frames, 'BLKUID')
    return [frame for frame_block_id, frame in zip(block_ids, frames) if frame_block_id == block_id]


def get_proposal_id(frames):
    proposal_ids = read_keywords_from_fits_files(frames, 'PROPID')
    return proposal_ids[0]


def get_first_guiding_frame(guider_frames):
    guider_states = read_keywords_from_fits_files(guider_frames, 'AGSTATE')
    guiding_frames = [frame for state, frame in zip(guider_states, guider_frames) if 'GUID' in state]
    guiding_frames.sort()
    return guiding_frames[0] if len(guiding_frames) > 0 else None


def get_guider_frames_for_science_exposure(guider_frames, ut_start, ut_stop):
    guider_starts = read_keywords_from_hdu_lists(guider_frames, 'DATE-OBS')
    return [frame for guider_start, frame in zip(guider_starts, guider_frames)
            if in_date_range(to_datetime(guider_start), ut_start, ut_stop)]


def convert_raw_fits_path_to_jpg(frame):
    return frame.replace('flash', 'flash' + os.path.sep + 'jpg').replace('.fits', '.jpg')
