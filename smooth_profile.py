import numpy as np
import time
import os
from numba import jit


def loadData(path):
    files = [name for name in os.listdir(path) if name.endswith('.dat')]
    data = []
    for fl in files:
        with open(os.path.join(path, fl), 'rb') as f:
            hdln = len(f.read()) - 2 * 600 * 592
            f.seek(0)
            shape = (600, 592)  # (r, c)
            data.append(np.fromstring(f.read()[hdln:], '<u2').reshape(shape))
    return np.dstack(data)


def smooth(inpt, window_len=10, window_type='flat'):
    """
    Smoothing function based on Scipy Cookbook recipe for data smoothing
    Uses predefined window function (selectable) to smooth a 1D data set
    Computes the convolution with a normalized window
    :param inpt: input list or 1d array
    :param window_len: even integer size of window
    :param window_type: string for type of window function
    :return otpt: 1d numpy array of smoothed data with same length as inpt
    """
    if not (window_len % 2 == 0):
        window_len += 1
        print('Window length supplied is odd - using next highest integer: {}.'.format(window_len))

    if window_len <= 3:
        print('Error in data smoothing - please select a larger window length')
        return

    # window_type = 'hanning'
    if not window_type in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
        print('Error - Invalid window_type')
        return

    # Generate two arguments to pass into numpy.convolve()
    # s is the input signal doctored with reflections of the input at the beginning and end
    # this serves to remove noise in the smoothing method
    # w is the window matrix based on pre-defined window functions or unit matrix for flat window

    s = np.r_[inpt[window_len-1:0:-1], inpt, inpt[-1:-window_len:-1]]
    # w = eval('np.'+window_type+'(window_len)')
    if window_type == 'flat':  # moving average
        w = np.ones(window_len, 'd')
    else:
        w = eval('np.'+window_type+'(window_len)')

    # create smoothed data via numpy.convolve using the normalized input window matrix
    otpt = np.convolve(w/w.sum(), s, mode='valid')

    # format otpt to be same size as inpt and return
    return otpt[int(window_len/2-1):-int(window_len/2)]


@jit
def smooth_loop(data):
    height = data.shape[0]
    width = data.shape[1]
    s = np.empty((600, 592), dtype=object)
    for row in range(height):
        for col in range(width):
            s[row, col] = smooth(data[row, col], window_type='flat', window_len=10)
    return s

@jit
def integrated_loop(data):
    # using flat window of length 10
    window_len = 10
    w = np.ones(window_len, 'd')
    out = np.empty((600, 592), dtype=object)

    for row in range(600):
        for col in range(592):
            inp = data[row, col, :]
            s = np.r_[inp[window_len-1:0:-1],inp,inp[-1:-window_len:-1]]
            smth = np.convolve(w/w.sum(), s, mode='valid')
            # format to original size
            smth = smth[int(window_len/2 -1):-int(window_len/2)]
            out[row, col] = smth


def main():
    ts = time.time()
    datapath = '/Users/Maxwell/Desktop/Ru_UNH_LEEM/141020/141020_03_LEEM-IV_50FOV/'
    data = loadData(datapath)
    print("Loaded data in {} seconds".format(time.time() - ts))

    ts = time.time()
    sdata = np.apply_along_axis(smooth, 2, data)
    print('Time to smooth array using apply_along_axis: {}'.format(time.time() - ts))

    ts = time.time()
    snumba = smooth_loop(data)
    print('Time to smooth array using nested loops with numba: {}'.format(time.time() - ts))

    ts = time.time()
    sint = integrated_loop(data)
    print("Time to smooth nested loops with integrated smoothing with numba {}".format(time.time() - ts))


if __name__ == '__main__':
    main()
