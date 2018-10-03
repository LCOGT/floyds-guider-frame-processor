from floyds_guider import utils
import logging
import os
import datetime
import astropy.io.fits as fits

logging.getLogger("floyds-guider-frames")

def test_get_cameras():
    known_guide_mapping = {'kb37': None,
                           'kb38': 'coj',
                           'kb42': 'ogg'}
    known_sci_mapping = {'floyds01':'ogg',
                         'floyds02':'coj'}

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

    headers = []
    headers.append(fits.Header([('AGSTATE', 'GUIDING_CLOSED_LOOP'), ('DATE-OBS', time_1)]))
    headers.append(fits.Header([('AGSTATE', 'ACQUIRING'), ('DATE-OBS', time_3)]))
    headers.append(fits.Header([('AGSTATE', 'ACQUIRING'), ('DATE-OBS', time_2)]))

    hdu_lists = [fits.HDUList(fits.PrimaryHDU(header=header)) for header in headers]

    first_acquisition_frame = utils.get_first_acquisition_frame(hdu_lists)

    assert utils.read_keywords_from_hdu_lists(first_acquisition_frame, 'DATE-OBS') == time_2

def test_get_science_exposures():
    headers = []
    headers.append(fits.Header([('OBSTYPE', 'SPECTRUM'), ('ID', 0)]))
    headers.append(fits.Header([('OBSTYPE', 'IMAGE'), ('ID', 1)]))
    headers.append(fits.Header([('OBSTYPE', 'IMAGE'), ('ID', 2)]))

    hdu_lists = [fits.HDUList(fits.PrimaryHDU(header=header)) for header in headers]
    science_frames = utils.get_science_exposures(hdu_lists)

    assert utils.read_keywords_from_hdu_lists(science_frames, 'ID') == [0]

def test_get_guider_frames_for_science_exposure():
    ut_start = utils.to_datetime('2018-09-08T08:21:40.549')
    ut_stop = utils.to_datetime('2018-09-08T08:31:40.549')

    headers = []
    headers.append(fits.Header([('DATE-OBS', '2018-09-08T08:25:40.549'), ('BLKUID', 0)]))
    headers.append(fits.Header([('DATE-OBS', '2018-09-08T08:37:40.549'), ('BLKUID', 1)]))

    guide_frames = [fits.HDUList(fits.PrimaryHDU(header=header)) for header in headers]

    guide_frames_for_exposure = utils.get_guider_frames_for_science_exposure(guide_frames, ut_start, ut_stop)

    assert utils.read_keywords_from_hdu_lists(guide_frames_for_exposure, 'BLKUID') == [0]

def test_get_tracking_guider_frames():
    headers = [fits.Header([('AGSTATE', 'GUIDING_CLOSED_LOOP'), ('ID', id)]) for id in range(0,4)]
    headers.append(fits.Header([('AGSTATE', 'ACQUIRING'), ('ID', 4)]))
    hdu_lists = [fits.HDUList(fits.PrimaryHDU(header=header)) for header in headers]

    tracking_frames = utils.get_tracking_guider_frames(hdu_lists)

    assert utils.read_keywords_from_hdu_lists(tracking_frames, 'ID') == [id for id in range (0,4)]

def test_read_keywords_from_hdu_lists():
    headers = [fits.Header([('BLKUID', id)]) for id in range(0,4)]
    hdu_lists = [fits.HDUList(fits.PrimaryHDU(header=header)) for header in headers]

    assert utils.read_keywords_from_hdu_lists(hdu_lists, 'BLKUID') == [id for id in range(0,4)]

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
        ut_start = utils.to_datetime(utils.read_keywords_from_hdu_lists(frame, 'DATE-OBS'))
        ut_stop = ut_start + datetime.timedelta(seconds=utils.read_keywords_from_hdu_lists(frame, 'EXPTIME'))

        block_id = utils.read_keywords_from_hdu_lists(frame, 'BLKUID')
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
