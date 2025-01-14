#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import open3d
import ros_numpy
import sensor_msgs.point_cloud2 as pc2
from numpy.lib import recfunctions
from sensor_msgs.msg import PointField
from std_msgs.msg import Header

# The data structure of each point in ros PointCloud2: 16 bits = x + y + z + rgb
FIELDS_XYZ = [
    PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
    PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
    PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
]
FIELDS_XYZRGB = FIELDS_XYZ + \
                [PointField(name='rgb', offset=12, datatype=PointField.FLOAT32, count=1)]


def to_msg(open3d_cloud, frame_id=None, stamp=None):
    header = Header()
    if stamp is not None:
        header.stamp = stamp
    if frame_id is not None:
        header.frame_id = frame_id

    o3d_asarray = np.asarray(open3d_cloud.points)

    o3d_x = o3d_asarray[:, 0]
    o3d_y = o3d_asarray[:, 1]
    o3d_z = o3d_asarray[:, 2]

    cloud_data = np.core.records.fromarrays([o3d_x, o3d_y, o3d_z], names='x,y,z')

    if not open3d_cloud.colors:  # XYZ only
        fields = FIELDS_XYZ
    else:  # XYZ + RGB
        fields = FIELDS_XYZRGB
        color_array = np.array(np.floor(np.asarray(open3d_cloud.colors) * 255), dtype=np.uint8)

        o3d_r = color_array[:, 0]
        o3d_g = color_array[:, 1]
        o3d_b = color_array[:, 2]

        cloud_data = np.lib.recfunctions.append_fields(cloud_data, ['r', 'g', 'b'], [o3d_r, o3d_g, o3d_b])

        cloud_data = ros_numpy.point_cloud2.merge_rgb_fields(cloud_data)

    return pc2.create_cloud(header, fields, cloud_data)


def split_rgba_field(cloud_arr):
    '''Takes an array with a named 'rgb' float32 field, and returns an array in which
    this has been split into 3 uint 8 fields: 'r', 'g', and 'b'.
 
    (pcl stores rgb in packed 32 bit floats)
    '''
    rgb_arr = cloud_arr['rgba'].copy()
    rgb_arr.dtype = np.uint32
    r = np.asarray((rgb_arr >> 16) & 255, dtype=np.uint8)
    g = np.asarray((rgb_arr >> 8) & 255, dtype=np.uint8)
    b = np.asarray(rgb_arr & 255, dtype=np.uint8)
     
    # create a new array, without rgb, but with r, g, and b fields
    new_dtype = []
    for field_name in cloud_arr.dtype.names:
        field_type, field_offset = cloud_arr.dtype.fields[field_name]
        if not field_name == 'rgb':
            new_dtype.append((field_name, field_type))
    new_dtype.append(('r', np.uint8))
    new_dtype.append(('g', np.uint8))
    new_dtype.append(('b', np.uint8))    
    new_cloud_arr = np.zeros(cloud_arr.shape, new_dtype)
    
    # fill in the new array
    for field_name in new_cloud_arr.dtype.names:
        if field_name == 'r':
            new_cloud_arr[field_name] = r
        elif field_name == 'g':
            new_cloud_arr[field_name] = g
        elif field_name == 'b':
            new_cloud_arr[field_name] = b
        else:
            new_cloud_arr[field_name] = cloud_arr[field_name]
    return new_cloud_arr

def from_msg(ros_cloud):
    xyzrgb_array = ros_numpy.point_cloud2.pointcloud2_to_array(ros_cloud)

    mask = np.isfinite(xyzrgb_array['x']) & np.isfinite(xyzrgb_array['y']) & np.isfinite(xyzrgb_array['z'])
    cloud_array = xyzrgb_array[mask]

    open3d_cloud = open3d.geometry.PointCloud()

    points = np.zeros(cloud_array.shape + (3,), dtype=np.float)
    points[..., 0] = cloud_array['x']
    points[..., 1] = cloud_array['y']
    points[..., 2] = cloud_array['z']
    open3d_cloud.points = open3d.utility.Vector3dVector(points)
    
    if 'rgb' in xyzrgb_array.dtype.names:
        rgb_array = ros_numpy.point_cloud2.split_rgb_field(xyzrgb_array)
        cloud_array = rgb_array[mask]

        colors = np.zeros(cloud_array.shape + (3,), dtype=np.float)
        colors[..., 0] = cloud_array['r']
        colors[..., 1] = cloud_array['g']
        colors[..., 2] = cloud_array['b']

        open3d_cloud.colors = open3d.utility.Vector3dVector(colors / 255.0)
        
    if 'rgba' in xyzrgb_array.dtype.names:
        rgb_array = split_rgba_field(xyzrgb_array)
        cloud_array = rgb_array[mask]

        colors = np.zeros(cloud_array.shape + (3,), dtype=np.float)
        colors[..., 0] = cloud_array['r']
        colors[..., 1] = cloud_array['g']
        colors[..., 2] = cloud_array['b']

        open3d_cloud.colors = open3d.utility.Vector3dVector(colors / 255.0)

    return open3d_cloud
