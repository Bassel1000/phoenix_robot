# Contributor: Bassel Elbahnasy
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    pkg_name = 'phoenix_description'
    pkg_share = get_package_share_directory(pkg_name)
    urdf_file_path = os.path.join(pkg_share, 'urdf', 'phoenix.urdf')

    with open(urdf_file_path, 'r') as infp:
        robot_desc = infp.read()

    # 1. State Publisher
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_desc, 'use_sim_time': True}]
    )
    # 1.5 Joint State Publisher (Fixes the red wheel errors)
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        parameters=[{'use_sim_time': True}]
    )

    # 2. Start Gazebo Harmonic with Custom World
    ros_gz_sim_dir = get_package_share_directory('ros_gz_sim')
    world_file_path = os.path.join(pkg_share, 'worlds', 'warehouse.sdf')
    
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim_dir, 'launch', 'gz_sim.launch.py')
        ),
        # Load the custom world file instead of empty.sdf
        launch_arguments={'gz_args': f'-r {world_file_path}'}.items()
    )
    # 3. Spawn Phoenix
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-topic', 'robot_description', '-name', 'phoenix'],
        output='screen'
    )

    # 4. Bridge ROS 2 and Gazebo Harmonic Topics
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist', 
            'scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',
            'phoenix/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image',
            '/model/phoenix/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V',
            '/model/phoenix/odometry@nav_msgs/msg/Odometry[gz.msgs.Odometry'
        ],
        remappings=[
            ('scan', '/scan'),
            ('phoenix/camera/image_raw', '/phoenix/camera/image_raw'),
            ('/model/phoenix/tf', '/tf'),
            ('/model/phoenix/odometry', '/odom')
           
        ],
        output='screen'
    )
    return LaunchDescription([
        robot_state_publisher_node,
        joint_state_publisher_node,
        gazebo,
        spawn_entity,
        bridge
    ])