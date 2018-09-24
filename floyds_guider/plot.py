from matplotlib import pyplot
from astropy.io import fits
import numpy as np
import logging
from xml.etree import ElementTree
from astropy.time import Time

logger = logging.getLogger('floyds-guider-frames')


def make_plot_for_webpage(x, y, xlabel, ylabel, output_filename):
    pyplot.clf()
    pyplot.plot(x, y, 'bo')
    pyplot.xlabel(xlabel)
    pyplot.ylabel(ylabel)
    pyplot.savefig(output_filename)


def read_keywords_from_guider_frames(guider_fits_file_paths, keyword):
    """Loops through the list of FITS guide frames, reading in
    the fits header keyword and returning this as a list"""

    header_values = []
    for guider_fits_filename in guider_fits_file_paths:
        header_values.append(fits.getval(guider_fits_filename, keyword=keyword))
    return header_values


def to_datetime(date_string):
    return Time(date_string).datetime


def in_date_range(date_to_check, start, end):
    taken_after_start = (to_datetime(date_to_check) - to_datetime(start)).total_seconds() > 0
    taken_before_end = (to_datetime(date_to_check) - to_datetime(end)).total_seconds() < 0
    return taken_after_start and taken_before_end


def get_guider_frames_during_exposure(guider_frames, ut_start, ut_stop):
    guider_start_times = read_keywords_from_guider_frames(guider_frames, 'DATE-OBS')
    taken_during_exposure = [True if in_date_range(start_time, ut_start, ut_stop) else False
                             for start_time in guider_start_times]
    return [guider_frame for guider_frame, should_use in zip(guider_frames, taken_during_exposure) if should_use]


def get_relative_guider_observation_times(guider_frames, ut_start):
    dates_of_guider_frames = [to_datetime(guider_date)
                              for guider_date in read_keywords_from_guider_frames(guider_frames, 'DATE-OBS')]
    guider_exposure_times = read_keywords_from_guider_frames(guider_frames, 'EXPTIME')
    return [(guider_frame_date - to_datetime(ut_start)).total_seconds() + guider_exposure_time / 2.0
            for guider_frame_date, guider_exposure_time in zip(dates_of_guider_frames, guider_exposure_times)]
        

def make_guide_info_plots(guider_frames, ut_start, ut_stop, output_basename):
    """Generate plots from FITS guide images"""

    guider_frames_for_exposure = get_guider_frames_during_exposure(guider_frames, ut_start, ut_stop)

    if len(guider_frames_for_exposure) == 0:
        logger.error('No guider frames taken during exposure!')
    else:
        relative_guider_times = get_relative_guider_observation_times(guider_frames_for_exposure, ut_start)
        guider_states = read_keywords_from_guider_frames(guider_frames_for_exposure, 'AGSTATE')

        guider_time_label = 'Guider Observation Time - {ut_start} (Seconds)'.format(ut_start=ut_start)
        make_plot_for_webpage(relative_guider_times, guider_states, guider_time_label,
                              'Guider State', output_basename + '_guidestate.png')

        xml_files = [f.replace('.fits', '.fits.guide.xml').replace('flash/', 'cat/')
                     for f in guider_frames_for_exposure]
        stats = read_stats_from_xml_files(xml_files)

        make_plot_for_webpage(relative_guider_times, stats['total_flux'], guider_time_label, 'Total Counts',
                              output_basename + '_guidecounts.png')

        make_plot_for_webpage(relative_guider_times, stats['x_center'], guider_time_label, 'X Center (pixels)',
                              output_basename + '_guidext.png')

        make_plot_for_webpage(relative_guider_times, stats['y_center'], guider_time_label, 'Y Center (pixels)',
                              output_basename + '_guideyt.png')

        make_plot_for_webpage(relative_guider_times, stats['fwhm'], guider_time_label, 'FWHM (pixels)',
                              output_basename + '_guidefwhmt.png')

        make_plot_for_webpage(stats['x_center'], stats['y_center'], 'X Center (pixels)', 'Y Center (pixels)',
                              output_basename + '_guidexy.png')


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
