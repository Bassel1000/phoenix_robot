import os
from setuptools import setup

package_name = 'phoenix_control'


os.makedirs('resource', exist_ok=True)
with open(os.path.join('resource', package_name), 'w') as f:
    f.write('marker')
# ---------------

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='bassel',
    maintainer_email='bassel@todo.todo',
    description='Edge hardware control nodes for Phoenix Robot',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'motor_controller = phoenix_control.motor_controller:main',
            'mqtt_nav_client = phoenix_control.mqtt_nav_client:main',
            'lidar_publisher = phoenix_control.lidar_publisher:main',
            'pump_controller = phoenix_control.pump_controller:main',
            'nozzle_controller = phoenix_control.nozzle_controller:main',
        ],
    },
)