import datetime
import os
from glob import glob
from xml.etree import ElementTree

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
            stats[keyword] = value
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


def get_files(path):
    frames = glob(path)
    # Reject empty fits files
    frames = [frame for frame in frames if os.path.getsize(frame) > MINIMUM_GOOD_FILE_SIZE]
    return frames


def get_default_dayobs(site):
    if 'ogg' in site:
        # Default day-obs is yesterday
        day_obs = datetime.datetime.now() - datetime.timedelta(days=1)
    else:
        day_obs = datetime.datetime.now()
    return day_obs.strftime('%Y%m%d')


def get_guider_frames_in_molecule(frames, molecule):
    molecule_ids = read_keywords_from_fits_files(frames, 'MOLUID')
    return [frame for molecule_id, frame in zip(molecule_ids, frames) if molecule_id == molecule]


def get_first_acquisition_frame(guider_frames):
    guider_states = read_keywords_from_fits_files(guider_frames, 'AGSTATE')
    acquisition_frames = [frame for state, frame in zip(guider_states, guider_frames) if 'ACQUIRING' in state]
    acquisition_frames.sort()
    return acquisition_frames[0]


def get_science_exposures(frames):
    obstypes = read_keywords_from_fits_files(frames, 'OBSTYPE')
    return [frame for obstype, frame in zip(obstypes, frames) if obstype == 'SPECTRUM']


def get_frames_in_block(frames, block_id):
    block_ids = read_keywords_from_fits_files(frames, 'BLKUID')
    return [frame for frame_block_id, frame in zip(block_ids, frames) if frame_block_id == block_id]


def get_proposal_id(frames):
    proposal_ids = read_keywords_from_fits_files(frames, 'PROPID')
    return proposal_ids[0]


def get_first_guiding_frame(guider_frames):
    guider_states = read_keywords_from_fits_files(guider_frames, 'AGSTATE')
    guiding_frames = [frame for state, frame in zip(guider_states, guider_frames) if 'GUID' in state]
    guiding_frames.sort()
    return guiding_frames[0]


def get_acquisition_and_first_guiding_images(floyds_frames, guider_frames):
    molecules = set(read_keywords_from_fits_files(floyds_frames, 'MOLUID'))

    molecule_frames = []
    for molecule in molecules:
        guider_frames_in_molecule = get_guider_frames_in_molecule(guider_frames, molecule)
        molecule_frames.append({'molecule_id': molecule,
                                'acquisition_image': get_first_acquisition_frame(guider_frames_in_molecule),
                                'first_guiding_frame': get_first_guiding_frame(guider_frames_in_molecule)})
    molecule_frames.sort(key=lambda element: element['molecule_id'])
    return molecule_frames


def get_guider_frames_for_science_exposure(guider_frames, ut_start, ut_stop):
    guider_starts = read_keywords_from_fits_files(guider_frames, 'DATE-OBS')
    return [frame for guider_start, frame in zip(guider_starts, guider_frames)
            if in_date_range(to_datetime(guider_start), ut_start, ut_stop)]
