import os
import sys
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')
import geopandas as gpd
import numpy as np
import pandas as pd
from tqdm import tqdm
import rasterio as rio
import rasterio.warp
import shapely

from tif_tiling import tile_tif
from osm_towers import add_geom_towers


logger = logging.getLogger('maxar.repo')
# logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.DEBUG)

# def safe_rio_open(fp):
#     try:
#         ds = rio.open(fp)
#         return ds
#     except:
#         logger.error(f'Error Opening {tif_file}')
#         raise IOError
#     finally:
#         try:
#             ds.close()
#         except:
#             pass

ALL_COUNTRY_DICT = { # Dict of all currently available imagery
            'australia': 'AU',
            'bangladesh': 'BD',
            'chad': 'TD',
            'drc': 'CD',
            'ghana': 'GH', 
            'malawi': 'MW',
            'sierra_leone': 'SL',
            'california': 'US-CA',
            'texas': 'US-TX',
            'brazil': 'BR',
            'south_africa':'ZA',
            'germany': 'DE',
            'philippines': 'PH'
            }

def get_utm_from_wgs(w_lon, s_lat, e_lon, n_lat):
    from pyproj import CRS
    from pyproj.aoi import AreaOfInterest
    from pyproj.database import query_utm_crs_info
    
    utm_crs_list = query_utm_crs_info(
        datum_name="WGS 84",
        area_of_interest=AreaOfInterest(
            west_lon_degree=w_lon,
            south_lat_degree=s_lat,
            east_lon_degree=e_lon,
            north_lat_degree=n_lat,
        ),
    )
    if len(utm_crs_list) == 0:
        logger.error('probably already in utm')
        return None
    utm_crs = CRS.from_epsg(utm_crs_list[0].code) # just return the first one for now
    return utm_crs.to_string()

def get_resolution(ds):
    utm_dst_crs = get_utm_from_wgs(*ds.bounds) if ds.crs.is_geographic else ds.crs
    transform, width, height = rio.warp.calculate_default_transform(ds.crs, utm_dst_crs, ds.width, ds.height, *ds.bounds)
    # logger.debug(f'x_res = {transform.a}, y_res = {-transform.e}')
    return(transform.a, -transform.e)
    

class maxarImagery:
    def __init__(self, tif_repo):
        self.c_dir = os.path.dirname(tif_repo)
        self.c_name = os.path.basename(self.c_dir)
        self.coverage_path = os.path.join(tif_repo, "coverage.geojson")
      
        if os.path.basename(tif_repo) == 'links':
            tif_links_files = [os.path.join(tif_repo, filename) for filename in os.listdir(tif_repo) if filename.endswith(".txt")]
            tif_links = []
            for tif_links_file in tif_links_files:
                with open(tif_links_file, 'r') as f:
                    for line in f.readlines():
                        if not 'vegetation' in line:
                            tif_links.append(line)
            
            self.tif_paths = tif_links
        
        elif os.path.basename(tif_repo) == 'raw':
            self.tif_paths = [os.path.join(tif_repo, filename) for filename in os.listdir(tif_repo) if filename.endswith(".tif")]
        elif os.path.basename(tif_repo).startswith('tif_tiles'):
            self.tif_paths = [os.path.join(tif_repo, filename) for filename in os.listdir(tif_repo) if filename.endswith(".tif")]
        else:
            raise NotImplementedError

    def get_info(self):
        for tif_file in self.tif_paths[0:1]:
            with rio.open(tif_file) as s:
                logger.info('\n'.join(['',
                    f'CRS = {s.crs}',
                    f'Width = {s.width}, Height = {s.height}',
                    f'{s.transform}',
                    f'Transform (Rasterio) {tuple(s.transform)}',
                    f'Transform (GDAL) {s.transform.to_gdal()}',
                    f'Transform (Shapely) {s.transform.to_shapely()}',
                    f'Tags = {s.tags()}',
                    f'Meta = {s.meta}',
                    f'Driver = {s.driver}',
                    # f'Dataset Mask = {s.dataset_mask()}',
                    f'Bounds = {s.bounds}',
                    f'Number of Bands = {s.count}'
                ]))

    def get_dir_resolution(self):
        for tif_file in self.tif_paths[0:1]:
            with rio.open(tif_file) as src:
                return get_resolution(src)

    
    def get_crs_code(self):
        for tif_file in self.tif_paths[0:1]: # CRS for all files in one CC are the same
            with rio.open(tif_file) as src:
                crs = src.crs
                # crs_code = str(crs.code)
                crs_code = str(crs['init']).split(':')[-1]
                logger.info(f'{crs_code}')
            return crs_code
    
    def get_tif_bounds(self, tif_file_path, dst_crs={'init': 'epsg:4326'}):
        if dst_crs is None:
            reproject = False
        else:
            reproject = True

        with rio.open(tif_file_path) as src:
            bounds = src.bounds
            raster_crs = src.crs
            if raster_crs != dst_crs and reproject is True:
                logger.debug(f"reprojecting crs from {src.crs} to {dst_crs}")
                bounds = rasterio.warp.transform_bounds(src.crs, dst_crs, *bounds)
                raster_crs = dst_crs
            geom = shapely.geometry.box(*bounds)
        return geom, raster_crs

    def generate_coverage(self, save=True):
        coverage = gpd.GeoDataFrame({"filename": [], "geometry": []})
        for tif_file in tqdm(self.tif_paths):
            poly, crs = self.get_tif_bounds(tif_file, dst_crs=None)
            coverage = coverage.append({"filename": tif_file, "geometry": poly}, ignore_index=True)
        coverage = coverage.set_crs(epsg=self.get_crs_code())
        if save:
            coverage.to_file(self.coverage_path, driver='GeoJSON')
        return coverage

    def get_coverage(self, cache=True):
        if not os.path.exists(self.coverage_path):
            self.generate_coverage(save=True)
        
        coverage = gpd.read_file(self.coverage_path)
        return coverage

    def get_joined_assets(self, gdf_assets):
        coverage = self.get_coverage()
        if gdf_assets.crs != coverage.crs:
            logger.debug(f'Assets CRS: {gdf_assets.crs}, Coverage CRS: {coverage.crs}, Reprojecting to Assets CRS')
        joined_assets = gpd.sjoin(gdf_assets, coverage.to_crs(gdf_assets.crs), how='inner')
        return joined_assets

    def get_file_point(self, gdf_assets):
        joined_assets = self.get_joined_assets(gdf_assets)
        file_point = joined_assets.groupby('filename')['geometry'].apply(list)
        return file_point


    def tile_tif_dir(self, gdf_assets, tile_width, tile_height, overlap, bounded, out_path = None):
        # tile_width, tile_height, overlap, bounded = 256, 256, 0, True
        out_path = os.path.dirname(self.c_dir) if out_path is None else out_path
        tile_path = os.path.join(out_path, self.c_name, f'tif_tiles_{tile_width}_{tile_height}_{overlap}')
        tile_path += '_B' if bounded else ''
        os.makedirs(tile_path, exist_ok=True)
        logger.debug(f'Tiling Tifs for {self.c_name} and saving to {tile_path}')

        gc = self.get_coverage()
        if gdf_assets.crs != gc.crs:
            logger.debug(f'Assets CRS: {gdf_assets.crs}, Coverage CRS: {gc.crs}, Reprojecting to Assets CRS')
        joined_assets = gpd.sjoin(gdf_assets, gc.to_crs(gdf_assets.crs), how='inner') # TODO: Project gdf_assets to gc
        file_point = joined_assets.groupby('filename')['geometry'].apply(list)
        for file_number, (tif_file, point_list) in enumerate(tqdm(file_point.iteritems(),total=file_point.shape[0]),1):
                point_series = gpd.GeoSeries(point_list, crs=joined_assets.crs)  # create GeoSeries of points
                prefix = os.path.join(tile_path, f'{self.c_name}_{file_number}_')
                try:
                    tile_tif(tif_file, point_series, prefix, tile_width, tile_height, overlap, bounded)
                except IOError:
                    logger.error(f'Excepted IOError for {tif_file}, skipping ...')
                    pass



class maxarRepo:
    def __init__(self, repo_path, sub_repo, osm_path, country_dict, cache_dir):
        self.repo_path = repo_path # './maxar_repo'
        self.sub_repo = sub_repo # 'raw', 'links', 'tif_tiles_X_X_X_X
        self.osm_path = osm_path
        self.cache_dir = cache_dir
        self.country_dict = ALL_COUNTRY_DICT
        if country_dict is not None:
            self.country_dict = country_dict
        else:
            self.country_dirs = os.listdir(self.repo_path)
            logger.error (print('missing regions in default dict', set(self.country_dirs) - set(self.country_dict.keys())))
        
        self.tif_dirs = [os.path.join(self.repo_path, c_name, self.sub_repo) for c_name in self.country_dict.keys()]

    def get_hv_towers(self, cache_dir = None):

            cache = True if cache_dir is not None else False
            if cache:
                if os.path.exists(os.path.join(cache_dir, 'cached_hv_towers.geojson')):
                    return gpd.read_file(os.path.join(cache_dir, 'cached_hv_towers.geojson'))

            # TODO: Move this function somewhere else
            # check if assets available
            for c_dir in self.country_dict.keys():
                if not os.path.exists(os.path.join(self.osm_path,f'{self.country_dict[c_dir]}_raw_towers.geojson')):
                    logger.error(f'asset not found for {c_dir} with code {self.country_dict[c_dir]}')
            
            asset_paths = [os.path.join(self.osm_path,f'{self.country_dict[c_dir]}_raw_towers.geojson') for c_dir in self.country_dict.keys()]
            tower_paths = [os.path.join(self.osm_path,f'{self.country_dict[c_dir]}_raw_towers.csv') for c_dir in self.country_dict.keys()]
            line_paths = [os.path.join(self.osm_path,f'{self.country_dict[c_dir]}_raw_lines.csv') for c_dir in self.country_dict.keys()]

            # Combine Tower GeoJSON to GeoPandas DF
            assets_all = gpd.GeoDataFrame()
            for asset_path in asset_paths:
                asset = gpd.read_file(asset_path)
                assets_all = assets_all.append(asset, ignore_index = True)
            assets_all = assets_all.set_crs(epsg='4326')

            # Combine Tower CSV to Pandas DF
            tower_all = pd.concat(map(pd.read_csv, tower_paths))

            # Combine Lines CSV to Pandas DF
            line_all = pd.concat(map(pd.read_csv, line_paths))

            gdf_hv_t = add_geom_towers(assets_all, tower_all, line_all, hv_thresh = 100000)

            if cache:
                gdf_hv_t.to_file(os.path.join(cache_dir, 'cached_hv_towers.geojson'), driver='GeoJSON')

            return gdf_hv_t

    def get_crs_dict(self):
        crs_dict = {}
        for tif_dir in self.tif_dirs:
            m_sat = maxarImagery(tif_dir)
            crs_code = m_sat.get_crs_code()
            crs_dict[m_sat.c_name] = str(crs_code)
        logger.info(crs_dict)
        return crs_dict

    def get_repo_resolution(self):
        # Check Resolution of Dataset
        for tif_dir in self.tif_dirs:
            m_sat = maxarImagery(tif_dir)
            x_res, y_res = m_sat.get_dir_resolution()
            logger.info(f'country: {m_sat.c_name}, x_res = {x_res}, y_res = {y_res}')

    def get_total_coverage(self):
        # coverage_paths = [os.path.join(ds_path,c_dir,'coverage.geojson') for c_dir in all_dict.keys()]
        total_coverage = gpd.GeoDataFrame()
        for tif_dir in self.tif_dirs:
            m_sat = maxarImagery(tif_dir)
            coverage = m_sat.get_coverage()
            coverage = coverage.to_crs(epsg='4326') # standardize crs
            total_coverage = total_coverage.append(coverage, ignore_index=True)
        return total_coverage

    def generate_all_tiles(self, tile_width, tile_height, overlap, bounded, out_path = None):
        hv_tower_assets = self.get_hv_towers(self.cache_dir)
        for tif_dir in self.tif_dirs:
            m_sat = maxarImagery(tif_dir)
            m_sat.tile_tif_dir(hv_tower_assets, tile_width, tile_height, overlap, bounded, out_path)



if __name__ == '__main__':
    tile_width, tile_height, overlap, bounded = 256, 256, 0, True

    # Dict for experiments (subset of all_dict)
    c_dict = {
        'gambia': 'GM',  #ARD
        'pakistan': 'PK',  #ARD
        # 'australia': 'AU', #0.38
        # 'bangladesh': 'BD',  # Low-Res 0.55
        # 'chad': 'TD',
        # 'drc': 'CD',
        # 'ghana': 'GH', # 0.37
        # 'malawi': 'MW',
        # 'sierra_leone': 'SL', # Low-Res 0.57
        # 'california': 'US-CA',
        # 'texas': 'US-TX',
        'south_africa':'ZA', #ARD
        # 'germany': 'DE',
        # 'philippines': 'PH'
        'sudan': 'SD', #ARD
        # 'afghanistan': 'AF', #ARD (links not working)
        'brazil': 'BR', #ARD
        'philippines': 'PH', #ARD

        }


    myMaxar = maxarRepo('./maxar_repo', 'links', './osm', c_dict, './')
    myMaxar.get_repo_resolution()
    # myMaxar.generate_all_tiles(tile_width, tile_height, overlap, bounded)

    # hv_tower_assets = myMaxar.get_hv_towers(cache_dir='./')
    # ghanaTif = maxarImagery('/home/matin/detect_energy/maxar_test/ghana/links')
    # # ghanaTif.tile_tif_dir(hv_tower_assets, tile_width, tile_height, overlap, bounded, './temp_tiles')
    # ghanaTif.get_coverage(True)
    # ghanaTif.tile_tif_dir(myMaxar.get_hv_towers('./'), tile_width, tile_height, overlap, bounded)


# sudo rclone mount mygrdrive:/PyPSA_Africa_images /mnt/gdrive --config=/home/matin/.config/rclone/rclone.conf --allow-other --drive-shared-with-me
# conda install -c conda-forge shapely rasterio pyproj pandas numpy geopandas


# Visualize Coverage

# import folium
# m = folium.Map(zoom_start=10, tiles='CartoDB positron')

# for _, r in total_coverage.iterrows():
#     # Without simplifying the representation of each borough,
#     # the map might not be displayed
#     # sim_geo = gpd.GeoSeries(r['geometry']).simplify(tolerance=0.001)
#     sim_geo = gpd.GeoSeries(r['geometry'])
#     geo_j = sim_geo.to_json()
#     geo_j = folium.GeoJson(data=geo_j,
#                            style_function=lambda x: {'fillColor': 'orange'})
#     # folium.Popup(r['BoroName']).add_to(geo_j)
#     geo_j.add_to(m)
# m