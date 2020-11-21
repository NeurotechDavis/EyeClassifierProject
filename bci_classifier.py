"""BCI Eye Classifier"""

# imports
import argparse
import numpy as np  # Module that simplifies computations on matrices
import matplotlib.pyplot as plt  # Module used for plotting
from pylsl import StreamInlet, resolve_byprop  # Module to receive EEG data
import os
import bci_helper as BCI
import socket

# intialize parameters
BUFFER_LENGTH   = 5
EPOCH_LENGTH    = 1
OVERLAP_LENGTH  = 0.8
SHIFT_LENGTH    = EPOCH_LENGTH - OVERLAP_LENGTH
TRAINING_LENGTH = 2


if __name__ == "__main__":

    # Parse Args
    parser = argparse.ArgumentParser(description='BCI Workshop example 2')
    parser.add_argument('channels', metavar='N', type=int, nargs='*',
    default =[0, 1, 2, 3],
    help ='channel number to use. If not specified, all the channels are used')

    args = parser.parse_args()
    channel_index = args.channels # ???

    # Connect to Muse
    print("Connecting...")
    streams = resolve_byprop('type', 'EEG', timeout = 2)
    inlet = StreamInlet(streams[0], max_chunklen=12)
    eeg_time_correction = inlet.time_correction()

    # Pull relevant information form stream
    info = inlet.info()
    desc = info.desc()
    freq = int(info.nominal_srate())
    n_channels = info.channel_count()

    # Record data to train classifier
    print('Recording Mental Activity 0')
    eeg_data0 = BCI.record_eeg(TRAINING_LENGTH, freq, channel_index)
    print('Recording Mental Activity 1')
    eeg_data1 = BCI.record_eeg(TRAINING_LENGTH, freq, channel_index)
    print('Recording Mental Activity 2')
    eeg_data2 = BCI.record_eeg(TRAINING_LENGTH, freq, channel_index)
    print('Recording Mental Activity 3')
    eeg_data3 = BCI.record_eeg(TRAINING_LENGTH, freq, channel_index)


    # Divide data into epochs
    epochs_0 = BCI.epoch_array(eeg_data0, EPOCH_LENGTH,
    OVERLAP_LENGTH * freq, freq)
    epochs_1 = BCI.epoch_array(eeg_data1, EPOCH_LENGTH,
    OVERLAP_LENGTH * freq, freq)
    epochs_2 = BCI.epoch_array(eeg_data2, EPOCH_LENGTH,
    OVERLAP_LENGTH * freq, freq)
    epochs_3 = BCI.epoch_array(eeg_data3, EPOCH_LENGTH,
    OVERLAP_LENGTH * freq, freq)

    # Compute corresponding feature matrices
    feat_matrix0 = BCI.compute_feature_matrix(epochs_0, freq)
    feat_matrix1 = BCI.compute_feature_matrix(epochs_1, freq)
    feat_matrix2 = BCI.compute_feature_matrix(epochs_2, freq)
    feat_matrix3 = BCI.compute_feature_matrix(epochs_3, freq)

    # Train Classifier
    [classifier, mu_ft, std_ft, score] = BCI.train_classifier(
    feat_matrix0, feat_matrix1,
    feat_matrix2, feat_matrix3,'RandomForestClassifier')


    print(str(score * 100) + '% correctly predicted')

    # Initialize buffers for real time data
    eeg_buffer       = np.zeros((int(freq * BUFFER_LENGTH), n_channels))
    print("eeg buffer")
    print(eeg_buffer.shape)
    filter_state     = None
    decision_buffer  = np.zeros((30, 1))

    # Plotter
    plotter_decision = BCI.DataPlotter(30, ['Decision'])

    # Initialize socket instance
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Create a port for the socket
    s.bind((socket.gethostname(), 1456))
    # Listen for an avaliable client for 5 seconds
    s.listen(5)

    # Start acquiring data and computing features
    try:
        while True:

            # Pull data
            eeg_data = BCI.record_eeg(SHIFT_LENGTH, freq, channel_index)

            ch_data = np.array(eeg_data)[:, channel_index]

            # Update EEG buffer
            eeg_buffer, filter_state = BCI.update_buffer(
            eeg_buffer, ch_data, apply_filter = True,
            filter_state = filter_state)

            # Get latest epoch
            epoch = BCI.get_last_data(eeg_buffer, EPOCH_LENGTH * freq)

            # Compute band powers
            band_powers = BCI.compute_band_powers(epoch, freq)

            # Use band powers to test classifier
            y_hat = BCI.test_classifier(classifier, band_powers.reshape(1, -1),
            mu_ft, std_ft)

            # Update decision buffer
            decision_buffer, _ = BCI.update_buffer(decision_buffer,
            np.reshape(y_hat, (-1, 1)))

            # accept client and get client IP
            clientsocket, address = s.accept()
            print("Connection has been established.")
            pred = np.mean(decision_buffer)
            # input for Raspberry Pi
            x = str(pred)
            print(x)

            # sends data
            clientsocket.send(bytes(x, 'utf-8'))

            # Visualize decisions
            plotter_decision.update_plot(decision_buffer)
            plt.pause(0.00001)

    except KeyboardInterrupt:

            print('Closing program')
