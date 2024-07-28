import os
import cv2
import sys
import numpy as np
import time
from pyorbbecsdk import *
from pyorbbecsdk import Pipeline, FrameSet, Config
import argparse
from examples.utils import frame_to_bgr_image
import threading
from queue import Queue

ESC_KEY = 27

class DepthCameraProcessor:
    def __init__(self, enable_sync=True, align_mode='HW', save_threshold=10):
        self.enable_sync = enable_sync
        self.align_mode = align_mode
        self.save_threshold = save_threshold
        self.pipeline = None
        self.device = None
        self.event = threading.Event()
        self.save_queue = Queue()
        self.folder_path = None  # Initialize folder path

    def create_directory_if_not_exists(self, directory):
        if not os.path.exists(directory):
            os.makedirs(directory)

    def save_color_image(self, color_image):
        timestamp = int(time.time() * 1000)  # Convert current time to milliseconds
        filename = os.path.join(self.save_rgb_dir, f"{timestamp}.jpg")
        cv2.imwrite(filename, color_image)
        # print(f"Color image saved at {filename}")

    def process_depth_data(self, depth_frame):
        if depth_frame is None:
            return None  # Return None for depth_data

        width = depth_frame.get_width()
        height = depth_frame.get_height()
        scale = depth_frame.get_depth_scale()
        # print(width, height, scale)

        depth_data = np.frombuffer(depth_frame.get_data(), dtype=np.uint16)
        depth_data = depth_data.reshape((height, width))
        depth_data = depth_data.astype(np.float32) * scale
        depth_data = depth_data.astype(np.uint16)
        
        return depth_data  # Return depth_data

    def save_depth_frame(self, depth_data):
        timestamp = int(time.time() * 1000)  # Convert current time to milliseconds
        filename = os.path.join(self.save_depth_dir, f"{timestamp}")
        depth_data = depth_data.astype(np.uint16)
        start = time.time()
        np.save(filename, depth_data)
        # depth_data.tofile(raw_filename)
        # print("saving time:", time.time()-start)
        # print(f"Depth data saved at {raw_filename}")

    def configure_pipeline(self):
        try:
            self.pipeline = Pipeline()
            self.device = self.pipeline.get_device()
            device_info = self.device.get_device_info()
            device_pid = device_info.get_pid()

            profile_list = self.pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
            color_profile = profile_list.get_default_video_stream_profile()
            config = Config()
            config.enable_stream(color_profile)

            profile_list = self.pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
            assert profile_list is not None
            depth_profile = profile_list.get_default_video_stream_profile()
            assert depth_profile is not None
            print("color profile : {}x{}@{}_{}".format(color_profile.get_width(),
                                                        color_profile.get_height(),
                                                        color_profile.get_fps(),
                                                        color_profile.get_format()))
            print("depth profile : {}x{}@{}_{}".format(depth_profile.get_width(),
                                                        depth_profile.get_height(),
                                                        depth_profile.get_fps(),
                                                        depth_profile.get_format()))
            config.enable_stream(depth_profile)

            # if self.align_mode == 'HW':
            #     if device_pid == 0x066B:
            #         config.set_align_mode(OBAlignMode.SW_MODE)
            #     else:
            #         config.set_align_mode(OBAlignMode.HW_MODE)
            # elif self.align_mode == 'SW':
            #     config.set_align_mode(OBAlignMode.SW_MODE)
            # else:
            #     config.set_align_mode(OBAlignMode.DISABLE)

            if self.enable_sync:
                self.pipeline.enable_frame_sync()

            self.pipeline.start(config)
            print(self.pipeline)
            return True
        except Exception as e:
            print(e)
            return False

    def process_frames(self, folder_path):
        self.folder_path = folder_path
        if self.pipeline is None or self.device is None:
            print("Pipeline or device not configured.")
            return

        serial_number = self.device.get_device_info().get_serial_number()
        print('serial_number:', serial_number)
        print('Saved at ', self.folder_path)
        
        if self.folder_path is None:
            return  # Skip if folder path is not set
        self.save_rgb_dir = os.path.join("/docker_disk/dataset", self.folder_path, "front_RGB")
        self.create_directory_if_not_exists(self.save_rgb_dir)
        self.save_depth_dir = os.path.join("/docker_disk/dataset", self.folder_path, "front_depth")
        self.create_directory_if_not_exists(self.save_depth_dir)

        def process_and_save(color_image, depth_data):
            self.save_color_image(color_image)
            self.save_depth_frame(depth_data)

        while True:
            try:
                frames: FrameSet = self.pipeline.wait_for_frames(100)
                if frames is None:
                    continue
                color_frame = frames.get_color_frame()
                depth_frame = frames.get_depth_frame()
                if color_frame is None or depth_frame is None:
                    continue
                
                color_image = frame_to_bgr_image(color_frame)
                if color_image is None:
                    print("Failed to convert frame to image")
                    continue

                depth_data = self.process_depth_data(depth_frame)
                if depth_data is None:
                    print("Failed to process depth data")
                    continue

                if not self.event.is_set():
                    # Process and save in a separate thread
                    threading.Thread(target=process_and_save, args=(color_image.copy(), depth_data.copy())).start()

            except KeyboardInterrupt:
                break

        self.pipeline.stop()

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mode",
                        help="align mode, HW=hardware mode,SW=software mode,NONE=disable align",
                        type=str, default='HW')
    parser.add_argument("-f", "--folder_path",
                        help="Folder path for saving images",
                        type=str, default='data')
    parser.add_argument("-s", "--enable_sync", help="enable sync", type=bool, default=True)
    args = parser.parse_args()
    
    processor = DepthCameraProcessor(enable_sync=args.enable_sync,
                                     align_mode=args.mode,
                                     save_threshold=args.save_threshold)
    
    if processor.configure_pipeline():
        processor.process_frames(folder_path=args.folder_path)

if __name__ == "__main__":
    print('here')
    main(sys.argv[1:])