#!/usr/bin/env python
# -*- coding: latin-1 -*-
import atexit
import codecs
import csv
import random
from os.path import join

import yaml
from psychopy import visual, event, logging, gui, core

from Adaptives.NUpNDown import NUpNDown
from misc.screen_misc import get_screen_res, get_frame_rate

# GLOBALS
STIM_SIZE = 30
VISUAL_OFFSET = 60
STIM_COLOR = '#606060'
KEYS = ['left', 'right']

RESULTS = list()
RESULTS.append(
    ['PART_ID', 'Trial', 'Stimuli', 'Version', 'Training', 'Training_level', 'FIXTIME', 'TIME','Correct', 
	'SOA','Reversal', 'Reversal_count', 'Latency', 'stim_name'])


class CorrectStim(object):  # Correct Stimulus Enumerator
    LEFT = 1
    RIGHT = 2


class QuestonVersion(object):
    FIRST_SHOWED = 'First_showed'
    FIRST_HIDDEN = 'First_hidden'


@atexit.register
def save_beh_results():
    with open(join('results', PART_ID + '_' + str(random.choice(range(100, 1000))) + '_beh.csv'), 'w') as beh_file:
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
        abort_with_error('Experiment finished by user! {} pressed.'.format(key))


def show_info(win, file_name, insert=''):
    """
    Clear way to show info message into screen.
    :param win:
    :return:
    """
    msg = read_text_from_file(file_name, insert=insert)
    msg = visual.TextStim(win, color=STIM_COLOR, text=msg, height=STIM_SIZE - 10, wrapWidth=SCREEN_RES['width'])
    msg.draw()
    win.flip()
    key = event.waitKeys(keyList=['f7', 'return', 'space', 'left', 'right'] + KEYS)
    if key == ['f7']:
        abort_with_error('Experiment finished by user on info screen! F7 pressed.')
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

    # === Scene init ===
    win = visual.Window(SCREEN_RES.values(), fullscr=True, monitor='testMonitor', units='pix', screen=0, color='black')
    event.Mouse(visible=False, newPos=None, win=win)  # Make mouse invisible
    FRAME_RATE = get_frame_rate(win)
    PART_ID = info['IDENTYFIKATOR'] + info[u'P\u0141EC'] + info['WIEK']
    logging.LogFile('results/' + PART_ID + '.log', level=logging.INFO)  # errors logging
    logging.info('FRAME RATE: {}'.format(FRAME_RATE))
    logging.info('SCREEN RES: {}'.format(SCREEN_RES.values()))

    pos_feedb = visual.TextStim(win, text=u'Poprawna odpowied\u017A', color=STIM_COLOR, height=40)
    neg_feedb = visual.TextStim(win, text=u'Niepoprawna odpowied\u017A', color=STIM_COLOR, height=40)
    no_feedb = visual.TextStim(win, text=u'Nie udzieli\u0142e\u015B odpowiedzi', color=STIM_COLOR, height=40)

    for proc_version in ['CIRCLES']: #'SQUARES',
        if proc_version == 'SQUARES':
            left_stim = visual.Rect(win, width=2 * STIM_SIZE, height=2 * STIM_SIZE, lineColor=STIM_COLOR,
                                    fillColor=STIM_COLOR, pos=(-1 * VISUAL_OFFSET, 0))
            right_stim = visual.Rect(win, width=2 * STIM_SIZE, height=2 * STIM_SIZE, lineColor=STIM_COLOR,
                                     fillColor=STIM_COLOR, pos=(1 * VISUAL_OFFSET, 0))
            question = u'Który kwadrat pojawil sie pierwszy?'
            version = QuestonVersion.FIRST_SHOWED

        elif proc_version == 'CIRCLES':
            left_stim = visual.Circle(win, radius=1 * STIM_SIZE, lineColor=STIM_COLOR, fillColor=STIM_COLOR,
                                      pos=(-1 * VISUAL_OFFSET, 0))
            right_stim = visual.Circle(win, radius=1 * STIM_SIZE, lineColor=STIM_COLOR, fillColor=STIM_COLOR,
                                       pos=(1 * VISUAL_OFFSET, 0))
            question = u'Które kolko zniknelo pierwsze?'
            version = QuestonVersion.FIRST_HIDDEN

        else:
            raise NotImplementedError('Procedures working only with Squares or Circles')

        fix_stim = visual.TextStim(win, text='+', height=100, color=STIM_COLOR)
        arrow_label = visual.TextStim(win, text=u"\u2190       \u2192", color=STIM_COLOR, height=30,
                                      pos=(0, -200))

        question_text = visual.TextStim(win, text=question, color=STIM_COLOR, height=20,
                                      pos=(0, -180))

        # === Load data, configure log ===

        response_clock = core.Clock()
        conf = yaml.load(open(proc_version + '_config.yaml'))

        # === Training ===
        training = list()
        for train_desc in conf['Training']:
            training.append([train_desc['soa']] * train_desc['reps'])

        show_info(win, join('.', proc_version + '_messages', 'before_training.txt'))

        correct_trials = 0
        idx = 0
        train_level = 0
        for level in training:
            train_level += 1
            for soa in level:
                idx += 1
                corr, rt, stim_name = run_trial(conf, version, fix_stim, left_stim, right_stim, soa, win, arrow_label,
                                                question_text, response_clock)
                corr = int(corr)
                correct_trials += corr
                RESULTS.append(
                    [PART_ID, idx, proc_version, version, 1, train_level, conf['FIXTIME'], conf['TIME'], corr, soa,
                     '-',
                     '-', rt, stim_name])
                ### FEEDBACK
                if corr == 1:
                    feedb_msg = pos_feedb
                elif corr == 0:
                    feedb_msg = neg_feedb
                else:
                    feedb_msg = no_feedb
                for _ in range(30):
                    feedb_msg.draw()
                    check_exit()
                    win.flip()

        train_corr = int((float(correct_trials) / len(training)) * 100)
        show_info(win, join('.', proc_version + '_messages', 'feedback.txt'), insert=str(train_corr))

        # === Experiment ===

        experiment = NUpNDown(start_val=conf['START_SOA'], max_revs=conf['MAX_REVS'])

        old_rev_count_val = -1
        for idx, soa in enumerate(experiment, idx):
            corr, rt, stim_name = run_trial(conf, version, fix_stim, left_stim, right_stim, soa, win, arrow_label,
                                            question_text, response_clock)
            experiment.set_corr(corr)
            level, reversal, revs_count = map(int, experiment.get_jump_status())
            if old_rev_count_val != revs_count:
                old_rev_count_val = revs_count
                rev_count_val = revs_count
            else:
                rev_count_val = '-'

            RESULTS.append(
                [PART_ID, idx, proc_version, version, 0, '-', conf['FIXTIME'], conf['TIME'], int(corr), soa,
                 reversal,
                 rev_count_val, rt, stim_name])

            if idx == conf['MAX_TRIALS']:
                break

    # === Cleaning time ===
    save_beh_results()
    logging.flush()
    show_info(win, 'end.txt')
    win.close()


def run_trial(config, version, fix_stim, left_stim, right_stim, soa, win, arrow_label,question_text, response_clock):
    trial_type = random.choice([CorrectStim.LEFT, CorrectStim.RIGHT])
    stim = left_stim if trial_type == CorrectStim.LEFT else right_stim
    stim_name = 'left' if trial_type == CorrectStim.LEFT else 'right'
    rt = -1.0
    for _ in range(config['FIXTIME']):  # Fixation cross
        fix_stim.draw()
        win.flip()
        check_exit()
    for _ in range(config['DELAY']):
        win.flip()
        check_exit()
    if version == QuestonVersion.FIRST_SHOWED:
        for _ in range(soa):  # just one stims showed
            stim.draw()
            win.flip()
            check_exit()
        for _ in range(config['TIME']):
            left_stim.draw()
            right_stim.draw()
            win.flip()
            check_exit()
    elif version == QuestonVersion.FIRST_HIDDEN:
        for _ in range(config['TIME']):
            left_stim.draw()
            right_stim.draw()
            win.flip()
            check_exit()
        for _ in range(soa):  # just one stims showed
            stim.draw()
            win.flip()
            check_exit()
    corr = False  # Used if timeout
    win.callOnFlip(response_clock.reset)
    event.clearEvents()
    for _ in range(config['RTIME']):  # Time for reaction
        arrow_label.draw()
        question_text.draw()
        win.flip()
        keys = event.getKeys(keyList=KEYS)
        if keys:
            corr = True if keys[0] == stim_name else False
            rt = response_clock.getTime()
            break
        check_exit()
    if version == QuestonVersion.FIRST_HIDDEN:  # Yep, I know, that's ugly
        corr = not corr
	
    return corr, rt, stim_name


if __name__ == '__main__':
    PART_ID = ''
    SCREEN_RES = get_screen_res()
    main()
