from matplotlib import pyplot
import logging

from floyds_guider import utils

logger = logging.getLogger('floyds-guider-frames')


def make_plot_for_webpage(x, y, xlabel, ylabel, output_filename, y_tick_label_rotation=0):
    pyplot.clf()
    pyplot.plot(x, y, 'bo')
    pyplot.xlabel(xlabel)
    pyplot.ylabel(ylabel)
    pyplot.yticks(rotation=y_tick_label_rotation)
    pyplot.tight_layout()
    pyplot.savefig(output_filename)


def make_guide_info_plots(guider_frames, ut_start, output_basename):
    """Generate plots from FITS guide images"""
    if len(guider_frames) == 0:
        logger.error('No guider frames taken during exposure!')
    else:
        relative_guider_times = utils.get_relative_guider_observation_times(guider_frames, ut_start)
        guider_states = utils.read_keywords_from_fits_files(guider_frames, 'AGSTATE')

        guider_time_label = 'Guider Observation Time - {ut_start} (Seconds)'.format(ut_start=ut_start)

        plot_file_names = {'guide_state': output_basename + '_guidestate.png',
                           'total_counts': output_basename + '_guidecounts.png',
                           'x_position': output_basename + '_guidext.png',
                           'y_position': output_basename + '_guideyt.png',
                           'position': output_basename + '_guidexy.png',
                           'fwhm': output_basename + '_guidefwhmt.png'}

        make_plot_for_webpage(relative_guider_times, guider_states, guider_time_label,
                              'Guider State', plot_file_names['guide_state'], y_tick_label_rotation=65)

        xml_files = [f.replace('.fits', '.fits.guide.xml').replace('flash/', 'cat/')
                     for f in guider_frames]
        stats = utils.read_stats_from_xml_files(xml_files)

        make_plot_for_webpage(relative_guider_times, stats['total_counts'], guider_time_label, 'Total Counts',
                              plot_file_names['total_counts'])

        make_plot_for_webpage(relative_guider_times, stats['x_center'], guider_time_label, 'X Center (pixels)',
                              plot_file_names['x_position'])

        make_plot_for_webpage(relative_guider_times, stats['y_center'], guider_time_label, 'Y Center (pixels)',
                              plot_file_names['y_position'])

        make_plot_for_webpage(relative_guider_times, stats['fwhm'], guider_time_label, 'FWHM (pixels)',
                              plot_file_names['fwhm'])

        make_plot_for_webpage(stats['x_center'], stats['y_center'], 'X Center (pixels)', 'Y Center (pixels)',
                              plot_file_names['position'])
        return plot_file_names
