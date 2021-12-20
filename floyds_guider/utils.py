import datetime
import logging
import os
import string
from glob import glob
from xml.etree import ElementTree

from astropy.io import fits
from astropy.time import Time

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


def read_stats_from_fits_files(fits_files):
    dx = read_keywords_from_fits_files(fits_files, 'AGDX')
    dy = read_keywords_from_fits_files(fits_files, 'AGDY')
    fwhm = []
    total_counts = []
    for file in fits_files:
        xml_file = file.replace('.fits', '.fits.guide.xml').replace('flash/', 'cat/')
        fwhm.append(extract_field_from_xml_file(xml_file, 'fwhmMedian'))
        total_counts.append(extract_field_from_xml_file(xml_file, 'peakPixelValue'))

    return {'total_counts': total_counts, 'x_center': dx, 'y_center': dy, 'fwhm': fwhm}


def extract_field_from_xml_file(xml_file, field):
    tree = ElementTree.parse(xml_file)
    peak_pixel_value = tree.findall(field)
    return float(peak_pixel_value.pop().text)


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
    return acquisition_frames[0] if len(acquisition_frames) > 0 else None


def get_science_exposures(frames):
    obstypes = read_keywords_from_fits_files(frames, 'OBSTYPE')
    return [frame for obstype, frame in zip(obstypes, frames) if obstype == 'SPECTRUM']


def get_frames_in_block(frames, block_id, object_name):
    block_ids = read_keywords_from_fits_files(frames, 'BLKUID')
    object_names = read_keywords_from_fits_files(frames, 'OBJECT')
    return [frame for frame_block_id, frame_object_name, frame in zip(block_ids, object_names, frames)
            if frame_block_id == block_id and frame_object_name == object_name]


def get_proposal_id(frames):
    proposal_ids = read_keywords_from_fits_files(frames, 'PROPID')
    return proposal_ids[0]


def get_first_guiding_frame(guider_frames):
    guider_states = read_keywords_from_fits_files(guider_frames, 'AGSTATE')
    guiding_frames = [frame for state, frame in zip(guider_states, guider_frames) if 'GUID' in state]
    guiding_frames.sort()
    return guiding_frames[0] if len(guiding_frames) > 0 else None


def get_guider_frames_for_science_exposure(guider_frames, ut_start, ut_stop):
    guider_starts = read_keywords_from_fits_files(guider_frames, 'DATE-OBS')
    return [frame for guider_start, frame in zip(guider_starts, guider_frames)
            if in_date_range(to_datetime(guider_start), ut_start, ut_stop)]


def convert_raw_fits_path_to_jpg(frame):
    return frame.replace('flash', 'flash' + os.path.sep + 'jpg').replace('.fits', '.jpg')
