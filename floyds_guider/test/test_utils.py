from floyds_guider import utils
import logging
import os

logging.getLogger("floyds-guider-frames")

def test_get_guider_cameras():
    known_mapping = {'kb37': None,
                     'kb38': 'coj',
                     'kb42': 'ogg'}

    camera_dict = utils.get_guider_camera_codes()
    for code in known_mapping.keys():
        assert camera_dict[code] == known_mapping[code]

def test_get_path():
    known_path = "/archive/engineering/ogg/kb42/20180924/raw/*"
    test_path = utils.get_path("ogg", "kb42", "20180924")

    assert known_path == test_path

def test_get_site_from_camera_code():
    good_camera_code = 'kb38'
    bad_camera_code = 'kb1337'

    assert utils.get_site_from_camera_code(good_camera_code) == 'coj'
    assert utils.get_site_from_camera_code(bad_camera_code) is None

def test_get_animation_from_frames():
    base_path = os.path.join("..", "test_data")
    image_directory = utils.get_path("ogg", "kb42", "20180907")
    test_directory = base_path + image_directory
    assert test_directory == "../test_data/archive/engineering/ogg/kb42/20180907/raw/*"

    all_frames = utils.get_hdu_lists(test_directory)
    assert len(all_frames) != 0
    unique_block_list = set(utils.read_keywords_from_hdu_lists(all_frames, 'BLKUID'))

    for block in unique_block_list:
        output_path = os.path.join('.', block)
        frames = utils.get_frames_in_block(all_frames, block)
        utils.create_animation_from_frames(frames, output_path)
