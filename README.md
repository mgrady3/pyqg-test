# LiveViewer: A program for rapid analysis of LEEM-I(V) data sets
## Author: Maxwell Grady
## Affiliation: University of New Hampshire Department of Physics - Pohl group
## Version 0.1.0
## Date - January 31, 2017

# Functionality:
LiveViewer provides ability to load a LEEM-I(V) data set visualize the LEEM realspace images.
Mouse movement in the image area tracks the position of the cursor within the image and automatically
extracts the LEEM-I(V) curve from that position in the data set.
Mouse clicks in the image area automatically generate a static plot of the I(V) curve from that
position in the image.
Plots can be saved to images by right clicking the plot area and navigating the contextual menu.
Plots can be panned and zoomed in real time.
By default the I(V) curves extracted by mouse movement are shown after smoothing, whereas
the static I(V) curves generated by clicking are displayed with raw data.

Data sets loaded by the program are described by an Experiment Config file written in YAML.
An example YAML file is provided with the source code for this program.

# Usage:
Execute the program by running 'python liveviewer.py'

# Requirements:
Python Version 2.7 or 3.4+ (No support for other legacy python version)
The following packages are required:

    * numpy
    * PyQt and Qt version 5+
    * pyqtgraph version 0.1+
    * pyyaml
    * PIL (Note: you should use Pillow, the Friendly Fork of PIL)

All required packages can be installed via Pip or Anaconda - the python distribution
and package manager provided by Continuum Analytics.

I suggest using Anaconda if you are not familiar with installing python and managing virtual environments.
