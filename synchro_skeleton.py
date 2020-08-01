#!/usr/bin/env python
# -*- coding: latin-1 -*-
import atexit
import codecs
import csv
import os
import random
from os.path import join

import numpy as np
import pylink
import yaml
from psychopy import core, event, gui, logging, monitors, visual

import u3
from Adaptives.NUpNDown import NUpNDown
from EyeLinkCoreGraphicsPsychoPy import EyeLinkCoreGraphicsPsychoPy

port = u3.U3()
FIO1 = 6701  # the address of line FIO1 (EEG)


# GLOBALS
DEBUG = True
TEXT_SIZE = 30
VISUAL_OFFSET = 90
KEYS = ['left', 'right']

RESULTS = list()
RESULTS.append(['PART_ID', 'Trial', 'Stimuli', 'Training', 'FIXTIME', 'MTIME', 'Correct', 'SOA',
                'Level', 'Reversal', 'Reversal_count', 'Latency', 'Rating'])


class CorrectStim(object):  # Correct Stimulus Enumerator
    LEFT = 1
    RIGHT = 2


class Triggers(object):
    CLEAR = 0xFF00
    FIXATION = 0xFF01
    STIMULI = 0xFF02
    MASK = 0xFF04
    REACTION = 0xFF08
    FINISHED = 0xFF10

# @atexit.register
def save_beh_results():
    with open(join('results', 'beh', PART_ID + "_" + str(random.choice(range(100, 1000))) + '_beh.csv'), 'w') as beh_file:
        beh_writer = csv.writer(beh_file)
        beh_writer.writerows(RESULTS)
    logging.flush()


def read_text_from_file(file_name, insert=''):
    """
    Method that read message from text file, and optionally add some
    dynamically generated info.
    :param file_name: Name of file to read
    :param insert:
    :return: message
    """
    if not isinstance(file_name, str):
        logging.error('Problem with file reading, filename must be a string')
        raise TypeError('file_name must be a string')
    msg = list()
    with codecs.open(file_name, encoding='utf-8', mode='r') as data_file:
        for line in data_file:
            if not line.startswith('#'):  # if not commented line
                if line.startswith('<--insert-->'):
                    if insert:
                        msg.append(insert)
                else:
                    msg.append(line)
    return ''.join(msg)


def check_exit(key='f7'):
    stop = event.getKeys(keyList=[key])
    if stop:
        abort_with_error(
            'Experiment finished by user! {} pressed.'.format(key))


def show_info(win, file_name, insert=''):
    """
    Clear way to show info message into screen.
    :param win:
    :return:
    """
    msg = read_text_from_file(file_name, insert=insert)
    msg = visual.TextStim(win, color='grey', text=msg,
                          height=TEXT_SIZE - 10, wrapWidth=SCREEN_RES[0])
    msg.draw()
    win.flip()
    key = event.waitKeys(
        keyList=['f7', 'return', 'space', 'left', 'right'] + KEYS)
    if key == ['f7']:
        abort_with_error(
            'Experiment finished by user on info screen! F7 pressed.')
    win.flip()


def abort_with_error(err):
    logging.critical(err)
    raise Exception(err)


def main():
    global PART_ID  # PART_ID is used in case of error on @atexit, that's why it must be global
    # === Dialog popup ===
    info = {'IDENTYFIKATOR': '', u'P\u0141EC': ['M', "K"], 'WIEK': '20'}
    dictDlg = gui.DlgFromDict(dictionary=info, title='Czas detekcji wzrokowej')
    if not dictDlg.OK:
        abort_with_error('Info dialog terminated.')
    PART_ID = info['IDENTYFIKATOR'] + info[u'P\u0141EC'] + info['WIEK']

    if DEBUG:
        tk = pylink.EyeLink(None)  # Simulation mode
    else:
        tk = pylink.EyeLink('100.1.1.1')

    port.writeRegister(6751, 0xFFFF)  # set FIO1 as output
    port.writeRegister(FIO1, Triggers.CLEAR)  # start low

    dataFileName = f"{PART_ID}.EDF"
    tk.openDataFile(dataFileName)
    # add personalized data file header (preamble text)
    tk.sendCommand(
        f"add_file_preamble_text 'Inspection Time EyeTracking EXP PART_ID: {PART_ID}'")

    # === Scene init ===
    # we need to set monitor parameters to use the different PsychoPy screen "units"
    mon = monitors.Monitor('myMonitor', width=53.0, distance=100.0)
    mon.setSizePix(SCREEN_RES)
    win = visual.Window(SCREEN_RES, fullscr=(not DEBUG), monitor=mon, color='black',
                        winType='pyglet', units='pix', screen=0, allowStencil=True)
    genv = EyeLinkCoreGraphicsPsychoPy(tk, win)

    # set background and foreground colors, (-1,-1,-1)=black, (1,1,1)=white
    genv.backgroundColor = (-1, -1, -1)
    genv.foregroundColor = (1, 1, 1)
    genv.enableBeep = True
    genv.targetSize = 32
    genv.calTarget = 'circle'

    pylink.openGraphicsEx(genv)

    tk.setOfflineMode()
    pylink.pumpDelay(100)

    # see Eyelink Installation Guide, Section 8.4: Customizing Your PHYSICAL.INI Settings
    tk.sendCommand("screen_pixel_coords = 0 0 %d %d" %
                   (scnWidth-1, scnHeight-1))
    # save screen resolution in EDF data, so Data Viewer can correctly load experimental graphics
    tk.sendMessage("DISPLAY_COORDS = 0 0 %d %d" % (scnWidth-1, scnHeight-1))
    # sampling rate, 250, 500, 1000, or 2000; this command is not supported for EyeLInk II/I trackers
    tk.sendCommand("sample_rate 1000")
    # detect eye events based on "GAZE" (or "HREF") data
    tk.sendCommand("recording_parse_type = GAZE")
    # Saccade detection thresholds: 0-> standard/coginitve, 1-> sensitive/psychophysiological
    tk.sendCommand("select_parser_configuration 0")
    # choose a calibration type, H3, HV3, HV5, HV13 (HV = horiztonal/vertical),
    tk.sendCommand("calibration_type = HV9")

    # tracker hardware, 1-EyeLink I, 2-EyeLink II, 3-Newer models (1000/1000Plus/Portable DUO)
    hardware_ver = tk.getTrackerVersion()

    # tracking software version
    software_ver = 0
    if hardware_ver == 3:
        tvstr = tk.getTrackerVersionString()
        vindex = tvstr.find("EYELINK CL")
        software_ver = float(tvstr.split()[-1])

    event.Mouse(visible=False, newPos=None, win=win)  # Make mouse invisible
    logging.LogFile(join('.', 'results', 'log',
                         f"{PART_ID}_{str(random.choice(range(100, 1000)))}.log"), level=logging.INFO)  # errors logging
    logging.info('FRAME RATE: {}'.format(FRAME_RATE))
    logging.info('SCREEN RES: {}'.format(SCREEN_RES))
    pos_feedb = visual.TextStim(
        win, text=u'Poprawna odpowied\u017A', color='grey', height=40)
    neg_feedb = visual.TextStim(
        win, text=u'Niepoprawna odpowied\u017A', color='grey', height=40)
    no_feedb = visual.TextStim(
        win, text=u'Nie udzieli\u0142e\u015B odpowiedzi', color='grey', height=40)
    show_info(win, join('.', 'messages', 'hello.txt'))

    # sample and event data saved in EDF data file
    tk.sendCommand(
        "file_event_filter = LEFT,RIGHT,FIXATION,SACCADE,BLINK,MESSAGE,BUTTON,INPUT")
    if software_ver >= 4:
        tk.sendCommand(
            "file_sample_data  = LEFT,RIGHT,GAZE,GAZERES,PUPIL,HREF,AREA,STATUS,HTARGET,INPUT")
    else:
        tk.sendCommand(
            "file_sample_data  = LEFT,RIGHT,GAZE,GAZERES,PUPIL,HREF,AREA,STATUS,INPUT")

    # sample and event data available over the link
    tk.sendCommand(
        "link_event_filter = LEFT,RIGHT,FIXATION,FIXUPDATE,SACCADE,BLINK,BUTTON,INPUT")
    if software_ver >= 4:
        tk.sendCommand(
            "link_sample_data  = LEFT,RIGHT,GAZE,GAZERES,PUPIL,HREF,AREA,STATUS,HTARGET,INPUT")
    else:
        tk.sendCommand(
            "link_sample_data  = LEFT,RIGHT,GAZE,GAZERES,PUPIL,HREF,AREA,STATUS,INPUT")

    msg = visual.TextStim(win, text='Press ENTER twice to calibrate the tracker\n' +
                                    'In the task, press any key to end a trial', color='grey')
    msg.draw()
    win.flip()
    event.waitKeys()
    tk.doTrackerSetup()

    for proc_version in ['SQUARES', 'CIRCLES']:
        left_stim = visual.ImageStim(win, image=join(
            '.', 'stims', f'{proc_version}_LEFT.bmp'))
        right_stim = visual.ImageStim(win, image=join(
            '.', 'stims', f'{proc_version}_RIGHT.bmp'))
        mask_stim = visual.ImageStim(win, image=join(
            '.', 'stims', f'{proc_version}_MASK.bmp'))
        # fix_stim = visual.TextStim(win, text='+', height=100, color='grey')
        fix_stim = visual.ImageStim(
            win, image=join('.', 'stims', 'PRE_STIMULI.bmp'))
        arrow_label = visual.TextStim(win, text=u"\u2190       \u2192", color='grey', height=30,
                                      pos=(0, -200))
        if proc_version == 'SQUARES':
            question = u'Gdzie pojawi\u0142 si\u0119 OBROCONY kwadrat?'
        elif proc_version == 'CIRCLES':
            question = u'Gdzie pojawi\u0142 si\u0119 WI\u0118KSZY okr\u0119g?'
        else:
            raise NotImplementedError(
                f'Stimulus type: {proc_version} not implemented.')

        question_text = visual.TextStim(win, text=question, color='grey', height=20,
                                        pos=(0, -180))

        # === Load data, configure log ===

        response_clock = core.Clock()
        conf = yaml.load(
            open(join('.', 'configs', f'{proc_version}_config.yaml')))

        show_info(win, join('.', 'messages',
                            f'{proc_version}_before_training.txt'))
        # === Training ===

        training = NUpNDown(
            start_val=conf['START_SOA'], max_revs=conf['MAX_REVS'])

        old_rev_count_val = -1
        correct_trials = 0
        soas = []
        for idx, soa in enumerate(training):
            corr, rt, rating = run_trial(conf, fix_stim, left_stim, mask_stim, right_stim, soa, win, arrow_label,
                                         question_text, response_clock, idx, tk)
            training.set_corr(corr)
            level, reversal, revs_count = map(int, training.get_jump_status())
            if reversal:
                soas.append(soa)
            if old_rev_count_val != revs_count:
                old_rev_count_val = revs_count
                rev_count_val = revs_count
            else:
                rev_count_val = '-'

            RESULTS.append(
                [PART_ID, idx, proc_version, 1, conf['FIXTIME'], conf['MTIME'], int(corr), soa, level, reversal,
                 rev_count_val, rt, rating])

            # FEEDBACK
            if corr == 1:
                feedb_msg = pos_feedb
                correct_trials += 1
            elif corr == 0:
                feedb_msg = neg_feedb
            else:
                feedb_msg = no_feedb
            for _ in range(30):
                feedb_msg.draw()
                check_exit()
                win.flip()

        # === experiment ===
        soa = int(np.mean(soas[:int(0.6 * len(soas))]))

        show_info(win, join('.', 'messages', f'{proc_version}_feedback.txt'))

        for idx in range(idx, conf['NO_TRIALS']+idx):
            corr, rt, rating = run_trial(conf, fix_stim, left_stim, mask_stim, right_stim, soa, win, arrow_label,
                                         question_text, response_clock, idx, tk)
            corr = int(corr)
            correct_trials += corr
            RESULTS.append(
                [PART_ID, idx, proc_version, 0, conf['FIXTIME'], conf['MTIME'], corr, soa, '-', '-',
                    '-', rt, rating])

    show_info(win, join('.', 'messages', 'end.txt'))

    # close the EDF data file and put the tracker in idle mode
    tk.setOfflineMode()
    pylink.pumpDelay(100)
    tk.closeDataFile()

    # download EDF file to Display PC and put it in local folder ('edfData')
    msg = 'EDF data is transfering from EyeLink Host PC...'
    edfTransfer = visual.TextStim(win, text=msg, color='grey')
    edfTransfer.draw()
    win.flip()
    pylink.pumpDelay(500)

    # make sure the 'edfData' folder is there, create one if not
    dataFolder = join('.', 'results', 'edfData')
    if not os.path.exists(dataFolder):
        os.makedirs(dataFolder)
    tk.receiveDataFile(dataFileName, dataFolder + os.sep + dataFileName)

    # clean
    save_beh_results()
    tk.close()
    logging.flush()
    core.quit()
    window.close()
    port.close()


def run_trial(config, fix_stim, left_stim, mask_stim, right_stim, soa, win, arrow_label, question_text, response_clock, trial_index, tk):
    trial_type = random.choice([CorrectStim.LEFT, CorrectStim.RIGHT])
    stim = left_stim if trial_type == CorrectStim.LEFT else right_stim
    stim_name = 'left' if trial_type == CorrectStim.LEFT else 'right'
    rt = -1.0
    # put the tracker in idle mode before we transfer the backdrop image
    tk.setOfflineMode()
    pylink.pumpDelay(100)

    # send the standard "TRIALID" message to mark the start of a trial
    tk.sendMessage('TRIALID %d' % trial_index)

    # record_status_message : show some info on the Host PC - OPTIONAL
    tk.sendCommand("record_status_message 'TRIAL: %d'" % trial_index)

    # drift check
    # the doDriftCorrect() function requires target position in integers
    # the last two arguments: draw_target (1-default, 0-user draw the target then call this function)
    #                         allow_setup (1-press ESCAPE to recalibrate, 0-not allowed)
    try:
        err = tk.doDriftCorrect(int(scnWidth/2), 0, 1, 1)
    except:
        tk.doTrackerSetup()

     # put the tracker in idle mode before we start recording
    tk.setOfflineMode()
    pylink.pumpDelay(100)

    # start recording
    # arguments: sample_to_file, events_to_file, sample_over_link, event_over_link (1-yes, 0-no)

    err = tk.startRecording(1, 1, 1, 1)
    pylink.pumpDelay(100)  # wait for 100 ms to cache some samples

    # which eye(s) are available: 0-left, 1-right, 2-binocular
    eyeTracked = tk.eyeAvailable()
    if eyeTracked == 2:  # use right eye data if tracking binocularly
        eyeTracked = 1

    tk.sendMessage("trial_run")
    core.wait(0.02)

    win.callOnFlip(tk.sendMessage, "trial_fixation")
    win.callOnFlip(port.writeRegister, FIO1, Triggers.FIXATION)
    for i in range(config['FIXTIME']):  # Fixation hexagon
        if i == 2:
            port.writeRegister(FIO1, Triggers.CLEAR)
        fix_stim.draw()
        win.flip()
        check_exit()

    win.callOnFlip(tk.sendMessage, "trial_stimuli")
    win.callOnFlip(port.writeRegister, FIO1, Triggers.STIMULI)
    for i in range(soa):  # Stimulus presentation
        if i == 2:
            port.writeRegister(FIO1, Triggers.CLEAR)
        stim.draw()
        win.flip()
        check_exit()
    
    win.callOnFlip(tk.sendMessage, "trial_mask")
    win.callOnFlip(port.writeRegister, FIO1, Triggers.MASK)
    for i in range(config['MTIME']):  # Mask presentation
        if i == 2:
            port.writeRegister(FIO1, Triggers.CLEAR)
        mask_stim.draw()
        win.flip()
        check_exit()

    corr = False  # Used if timeout
    win.callOnFlip(response_clock.reset)
    win.callOnFlip(tk.sendMessage, "trial_reaction")
    win.callOnFlip(port.writeRegister, FIO1, Triggers.REACTION)
    event.clearEvents()
    for i in range(config['RTIME']):  # Time for reaction
        if i == 2:
            port.writeRegister(FIO1, Triggers.CLEAR)
        arrow_label.draw()
        question_text.draw()
        win.flip()
        keys = event.getKeys(keyList=KEYS)
        if keys:
            corr = True if keys[0] == stim_name else False
            rt = response_clock.getTime()
            break
        check_exit()
    # Rating Scale

    tk.sendMessage('trial_finished')
    port.writeRegister(FIO1, Triggers.FINISHED)
    core.wait(0.02)
    port.writeRegister(FIO1, Triggers.CLEAR)
    # clear the screen
    win.flip()
    tk.sendMessage('blank_screen')

    # stop recording
    tk.stopRecording()
    # clear the host display, this command is needed if you have backdrop image on the Host
    tk.sendCommand('clear_screen 0')
    # send over the standard 'TRIAL_RESULT' message to mark the end of trial
    tk.sendMessage('TRIAL_RESULT 0')

    ratingScale = visual.RatingScale(win, size=0.8, noMouse=True,
                                     markerStart=2, stretch=1.4, scale="Okre\u015bl swoj\u0105 pewno\u015b\u0107 co do udzielonej odpowiedzi", acceptPreText='Wybierz', choices=["\u017badna", "Ma\u0142a", "Du\u017ca", "Ca\u0142kowita"])
    while ratingScale.noResponse:
        ratingScale.draw()
        win.flip()
    rating = ratingScale.getRating()
    win.flip()
    # break + jitter
    wait_time_in_secs = 1 + random.choice(range(0, 120)) / 60.0
    core.wait(wait_time_in_secs)
    return corr, rt, rating


if __name__ == '__main__':
    PART_ID = ''
    scnWidth, scnHeight = SCREEN_RES = [1920, 1080]
    FRAME_RATE = 60
    main()
