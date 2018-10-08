from floyds_guider import utils
import logging
import os
import datetime
import astropy.io.fits as fits

logging.getLogger("floyds-guider-frames")

def test_get_cameras():
    known_guide_mapping = {None:'kb37',
                           'coj':'kb38',
                           'ogg':'kb42'}
    known_sci_mapping = {'ogg':'floyds01',
                         'coj':'floyds02'}

    #13 = all floyds autoguider cameras
    #4 = all floyds sci-cams
    guide_camera_dict = utils.get_camera_codes("http://configdb.lco.gtn/cameras/", 13)
    sci_camera_dict = utils.get_camera_codes("http://configdb.lco.gtn/cameras/", 4)

    for code in known_guide_mapping.keys():
        assert guide_camera_dict[code] == known_guide_mapping[code]

    for code in known_sci_mapping.keys():
        assert sci_camera_dict[code] == known_sci_mapping[code]

def test_get_path():
    known_path = "/archive/engineering/ogg/kb42/20180924/raw/*"
    test_path = utils.get_path("ogg", "kb42", "20180924")

    assert known_path == test_path

def test_get_good_frames_from_path():
    base_path = os.path.join("..", "test_data")
    floyds_image_directory = utils.get_path("ogg", "floyds01", "20180907")

    full_path = base_path + floyds_image_directory
    hdu_lists = utils.get_good_frames_from_path(full_path)

    for hdu_list in hdu_lists:
        assert isinstance(hdu_list, fits.hdu.hdulist.HDUList)
    assert len(hdu_lists) == 10

def test_get_site_from_camera_code():
    good_camera_code = 'kb38'
    bad_camera_code = 'kb1337'

    assert utils.get_site_from_camera_code(good_camera_code) == 'coj'
    assert utils.get_site_from_camera_code(bad_camera_code) is None

def test_get_first_acquisition_frame():
    time_1 = '2018-09-08T08:21:40.549'
    time_2 = '2018-09-08T08:31:40.549'
    time_3 = '2018-09-08T08:41:40.549'

    header_info = ([('AGSTATE', 'GUIDING_CLOSED_LOOP'), ('DATE-OBS', time_1)],
                   [('AGSTATE', 'ACQUIRING'), ('DATE-OBS', time_3)],
                   [('AGSTATE', 'ACQUIRING'), ('DATE-OBS', time_2)])

    test_frames = create_test_frames_from_header_info(header_info)
    first_acquisition_frame = utils.get_first_acquisition_frame(test_frames)

    assert utils.read_keywords_from_frames(first_acquisition_frame, 'DATE-OBS') == time_2

def test_get_science_exposures():

    header_info = ([('OBSTYPE', 'SPECTRUM'), ('ID', 0)],
                   [('OBSTYPE', 'IMAGE'), ('ID', 1)],
                   [('OBSTYPE', 'IMAGE'), ('ID', 2)],
                   [('OBSTYPE', 'SPECTRUM'), ('ID', 3)])

    test_frames = create_test_frames_from_header_info(header_info)
    science_frames = utils.get_science_exposures(test_frames)

    assert utils.read_keywords_from_frames(science_frames, 'ID') == [0, 3]

def test_get_guider_frames_for_science_exposure():
    ut_start = utils.to_datetime('2018-09-08T08:21:40.549')
    ut_stop = utils.to_datetime('2018-09-08T08:31:40.549')

    header_info = ([('DATE-OBS', '2018-09-08T08:25:40.549'), ('BLKUID', 0)],
                   [('DATE-OBS', '2018-09-08T08:37:40.549'), ('BLKUID', 1)],
                   [('DATE-OBS', '2018-09-08T08:22:43.549'), ('BLKUID', 2)])

    test_frames = create_test_frames_from_header_info(header_info)
    guide_frames_for_exposure = utils.get_guider_frames_for_science_exposure(test_frames, ut_start, ut_stop)

    assert utils.read_keywords_from_frames(guide_frames_for_exposure, 'BLKUID') == [0, 2]

def test_get_tracking_guider_frames():
    header_info = [[('AGSTATE', 'GUIDING_CLOSED_LOOP'), ('ID', id)] for id in range(0,4)]
    header_info.append([('AGSTATE', 'ACQUIRING'), ('ID', 4)])

    test_frames = create_test_frames_from_header_info(header_info)
    tracking_frames = utils.get_tracking_guider_frames(test_frames)

    assert utils.read_keywords_from_frames(tracking_frames, 'ID') == [id for id in range (0,4)]

def test_read_keywords_from_frames():
    headers = [[('BLKUID', id)] for id in range(0,4)]
    test_frames = create_test_frames_from_header_info(headers)

    assert utils.read_keywords_from_frames(test_frames, 'BLKUID') == [id for id in range(0,4)]

#End-to-end test
def test_get_animation_from_frames():
    base_path = os.path.join("..", "test_data")
    guide_image_directory = utils.get_path("ogg", "kb42", "20180907")
    floyds_image_directory = utils.get_path("ogg", "floyds01", "20180907")

    test_guide_directory = base_path + guide_image_directory
    test_sci_directory = base_path + floyds_image_directory

    all_guide_frames = utils.get_good_frames_from_path(test_guide_directory)
    all_floyds_frames = utils.get_good_frames_from_path(test_sci_directory)

    assert len(all_guide_frames) != 0
    assert len(all_floyds_frames) != 0

    frames_tracking = utils.get_tracking_guider_frames(all_guide_frames)
    frames_science = utils.get_science_exposures(all_floyds_frames)

    for frame in frames_science:
        ut_start = utils.to_datetime(utils.read_keywords_from_frames(frame, 'DATE-OBS'))
        ut_stop = ut_start + datetime.timedelta(seconds=utils.read_keywords_from_frames(frame, 'EXPTIME'))

        block_id = utils.read_keywords_from_frames(frame, 'BLKUID')
        output_path = os.path.join('.', block_id + '_' + ut_start.strftime("%X"))
        frames_to_animate = utils.get_guider_frames_for_science_exposure(frames_tracking,
                                                                         ut_start,
                                                                         ut_stop)

        #don't create blank animations
        if len(frames_to_animate) == 0:
            continue
        utils.create_animation_from_frames(frames_to_animate, output_path)
        assert os.path.exists(output_path + ".gif")
        assert os.path.getsize(output_path + ".gif") > 500000

def create_test_frames_from_header_info(header_info_lists):
    """
    Given a list of of header key-value pair lists, create test frames
    """
    headers = []
    for list in header_info_lists:
        headers.append(fits.Header(list))

    return [fits.HDUList(fits.PrimaryHDU(header=header)) for header in headers]
