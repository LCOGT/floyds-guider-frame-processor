import os
from xml.etree import ElementTree

import numpy as np
from astropy.io import fits
from astropy.time import Time

from floyds_guider.main import logger
from floyds_guider.plot import logger
import string


def convert_to_safe_filename(unsafe_string):
    valid_filename_characters = "-_.(){letters}{numbers}".format(letters=string.ascii_letters, numbers=string.digits)
    return ''.join(character for character in unsafe_string if character in valid_filename_characters)


def read_keywords_from_fits_files(fits_file_paths, keyword):
    """Loops through the list of FITS guide frames, reading in
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


def link_frames_to_images_directory(frames, image_directory):
    """
    Link the jpg and fits files for both spectra and guiders into the images directory
    """
    if not os.path.exists(image_directory):
        os.mkdir(image_directory)
    for frame in frames:
        try:
            os.symlink(frame, image_directory)
        except Exception as e:
            logger.error('Could not link {frame}: {exception}'.format(frame=frame, exception=e))
        # Also copy over the corresponding jpg file
        try:
            jpg_file = frame.replace('flash', 'flash' + os.path.sep + 'jpg').replace('.fits', '.jpg')
            os.symlink(jpg_file, image_directory)
        except Exception as e:
            logger.error('Could not link {frame}: {exception}'.format(frame=jpg_file, exception=e))
