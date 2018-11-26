"""
floyds-guider-frame-processor
Processor for FLOYDS guider frames

Author
    Curtis McCully (cmccully@lco.global)

License
    GPL v3.0
September 2018
"""
from setuptools import setup, find_packages


setup(name='floyds-guider-frame-processor',
      author=['Curtis McCully'],
      author_email=['cmccully@lco.global'],
      version='0.0.3',
      zip_safe=False,
      packages=find_packages(),
      install_requires=['numpy', 'matplotlib', 'astropy', 'lcogt_logging', 'jinja2'],
      entry_points={'console_scripts': ['process-floyds-guider=floyds_guider.main:process_guider_frames']})
