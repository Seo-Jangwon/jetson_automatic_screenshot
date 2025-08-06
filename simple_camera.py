import cv2
import os
import time
from datetime import datetime

""" 
gstreamer_pipeline returns a GStreamer pipeline for capturing from the CSI camera
Flip the image by setting the flip_method (most common values: 0 and 2)
display_width and display_height determine the size of each camera pane in the window on the screen
Default 1920x1080 displayd in a 1/4 size window
"""

def gstreamer_pipeline(
    sensor_id=0,
    capture_width=1280,
    capture_height=720,
    display_width=720,
    display_height=1280,
    framerate=60,
    flip_method=3,
):
    return (
        "nvarguscamerasrc sensor-id=%d ! "
        "video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
        % (
            sensor_id,
            capture_width,
            capture_height,
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )


def show_camera():
    window_title = "CSI Camera"

    # To flip the image, modify the flip_method parameter (0 and 2 are the most common)
    video_capture = cv2.VideoCapture(gstreamer_pipeline(flip_method=2, display_width=1600, display_height=900), cv2.CAP_GSTREAMER)
    if video_capture.isOpened():
        try:
            window_handle = cv2.namedWindow(window_title, cv2.WINDOW_AUTOSIZE)
            while True:
                ret_val, frame = video_capture.read()
                # Check to see if the user closed the window
                # Under GTK+ (Jetson Default), WND_PROP_VISIBLE does not work correctly. Under Qt it does
                # GTK - Substitute WND_PROP_AUTOSIZE to detect if window has been closed by user
                if cv2.getWindowProperty(window_title, cv2.WND_PROP_AUTOSIZE) >= 0:
                    cv2.imshow(window_title, frame)
                else:
                    break 
                keyCode = cv2.waitKey(10) & 0xFF
                # Stop the program on the ESC key or 'q'
                if keyCode == 27 or keyCode == ord('q'):
                    break
        finally:
            video_capture.release()
            cv2.destroyAllWindows()
    else:
        print("Error: Unable to open camera")


def capture_single_image(capture_timing):
    video_capture = cv2.VideoCapture(gstreamer_pipeline(flip_method=3), cv2.CAP_GSTREAMER)
    if video_capture.isOpened():
        try:
            for i in range(capture_timing):
                ret_val, frame = video_capture.read()
                if i == capture_timing-1:
                    video_capture.release()
                    return frame
        finally:
            video_capture.release()
    else:
        print("Error: Unable to open camera")


def capture_time_series_image(camera, crop, cap_time, target, titer):
    # 3sec is minimum start time
    window_title = "Camera " + str(camera)
    
    dst = './sample/'+target+'/'+titer
    os.makedirs(dst, exist_ok=True)
    folder_list = []
    
    video_capture = cv2.VideoCapture(gstreamer_pipeline(sensor_id=camera), cv2.CAP_GSTREAMER)
    
    start_capture = float(0)
    capture_flag = False
    
    xmin = crop['xmin']
    ymin = crop['ymin']
    w = crop['width']
    h = crop['height']

    start_time = cap_time['start']
    interval_1 = cap_time['interval_1']
    middle_time = cap_time['middle']
    interval_2 = cap_time['interval_2']
    end_time = cap_time['end']
    
    part1_timing = start_time
    part2_timing = middle_time

    if video_capture.isOpened():
        try:
            window_handle = cv2.namedWindow(window_title, cv2.WINDOW_AUTOSIZE)
            while True:
                keyCode = cv2.waitKey(10) & 0xFF
                # Stop the program on the ESC key or 'q'
                if keyCode == 27 or keyCode == ord('q'):
                    break
                elif not capture_flag:
                    if keyCode == ord('s'):
                        start_capture = time.time()
                        capture_flag = True
                        folder_list = os.listdir(dst)
                        os.makedirs(dst +'/'+str(len(folder_list)), exist_ok=True)
                        print('---------Capture Start---------')
                    elif keyCode == ord('j') and xmin>=10:
                        xmin -= 10
                    elif keyCode == ord('i') and ymin>=10:
                        ymin -= 10
                    elif keyCode == ord('l') and (xmin+w)<=(720-10):
                        xmin += 10
                    elif keyCode == ord('k') and (ymin+h)<=(1280-10):
                        ymin += 10

                timing = time.time()
                ret_val, frame = video_capture.read()
                if not ret_val or frame is None:
                    print("Frame is not available, skip...")
                    continue
                save_frame = frame[ymin:ymin+h,xmin:xmin+w,:]

                if capture_flag:
                    if start_time < (timing - start_capture) <= middle_time:
                        if (timing-start_capture) >= part1_timing:
                            cv2.imwrite(dst +'/'+str(len(folder_list))+'/'+str(round(part1_timing,2))+'.png', save_frame)
                            print('Capture ' + str(round(part1_timing,2))+'.png')
                            print('Real time: '+str(round(timing-start_capture,3))+'sec')
                            part1_timing += interval_1
                    elif middle_time < (timing - start_capture) <= end_time + 0.1:
                        if (timing-start_capture) >= part2_timing:
                            cv2.imwrite(dst +'/'+str(len(folder_list))+'/'+str(round(part2_timing,2))+'.png', save_frame)
                            print('Capture ' + str(round(part2_timing,2))+'.png')
                            print('Real time: '+str(round(timing-start_capture,3))+'sec')
                            part2_timing += interval_2
                    elif (timing - start_capture) > end_time + 0.1:
                        capture_flag = False
                        start_capture = float(0)
                        part1_timing = start_time
                        part2_timing = middle_time
                        print('----------Capture End----------')
                if cv2.getWindowProperty(window_title, cv2.WND_PROP_AUTOSIZE) >= 0:
                    display_frame = cv2.resize(save_frame, dsize=(0,0), fx=0.7, fy=0.7, interpolation=cv2.INTER_LINEAR)
                    cv2.imshow(window_title, display_frame)
                    continue
                else:
                    break 
        finally:
            video_capture.release()
            cv2.destroyAllWindows()
    else:
        print("Error: Unable to open camera")

