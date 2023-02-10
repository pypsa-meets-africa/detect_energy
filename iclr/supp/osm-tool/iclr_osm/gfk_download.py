__author__ = "Anonymous Author"
__copyright__ = "Copyright 2022, Anonymous Authors"
__license__ = ""

"""Geofabrik Data Download

This module contains functions to download Geofabrik data.

"""


import hashlib
import logging
import os
import shutil

import requests
import urllib3
from tqdm.auto import tqdm

logger = logging.getLogger("osm_geo")
logger.setLevel(logging.INFO)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def earth_downloader(url, dir, exists_ok=False):
    """
    Download file from url to dir

    Args:
        url (str): url to download
        dir (str): directory to download to

    Returns:
        str: filepath of downloaded file
    """
    filename = os.path.basename(url)
    filepath = os.path.join(dir, filename)
    if os.path.exists(filepath) and exists_ok:
        logger.debug(f'{filepath} already exists')
        return filepath
    logger.info(f"{filename} downloading to {filepath}")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)  #  create download dir
    with requests.get(url, stream=True, verify=False) as r:
        if r.status_code == 200:
            # url properly found, thus execute as expected
            file_size = int(r.headers.get('Content-Length', 0))
            desc = "(Unknown total file size)" if file_size == 0 else ""
            with tqdm.wrapattr(r.raw, "read", total=file_size, desc=desc, leave=False) as raw:
                with open(filepath, "wb") as f:
                    shutil.copyfileobj(raw, f)
        else:
            # error status code: file not found
            logger.error(
                f"Error code: {r.status_code}. File {filename} not downloaded from {url}"
            )
            filepath = None
    return filepath

# TODO: fix update param
def download_pbf(url, update, data_dir):

    pbf_dir = os.path.join(data_dir, "pbf")
    pbf_filename = os.path.basename(url)
    pbf_filepath = os.path.join(pbf_dir, pbf_filename)

    # TODO: multi-part download each file for parallel downloading... (pip install pySmartDL)
    if not os.path.exists(pbf_filepath):
        # download file
        d_filepath = earth_downloader(url, pbf_dir)
        assert d_filepath == pbf_filepath
    else:
        logger.debug(f"{pbf_filename} already exists in {pbf_filepath}")

    return pbf_filepath



def download_sitemap(geom, pkg_data_dir):
    geofabrik_geo = "https://download.geofabrik.de/index-v1.json"
    geofabrik_nogeo = "https://download.geofabrik.de/index-v1-nogeom.json"
    geofabrik_sitemap_url = geofabrik_geo if geom else geofabrik_nogeo

    sitemap_file = earth_downloader(geofabrik_sitemap_url, pkg_data_dir, exists_ok=True)

    return sitemap_file