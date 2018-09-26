from floyds_guider import utils
import logging

logging.getLogger("floyds-guider-frames")

def test_get_guider_cameras():
    known_camera_codes = ['kb37', 'kb38', 'kb42']
    camera_dict = utils.get_guider_cameras()

    for code in known_camera_codes:
        assert code in camera_dict.values()
