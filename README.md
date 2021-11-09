# Qontrol API

Integrated photonic devices need large-scale, precise electronic control. We can provide the precision and power you need, at a scale only limited by your ambition. Let’s take photonics into the future.
 See [our website](https://qontrol.co.uk/) for more details!

Python Library for interfacing with **Qontrol** integrated optics control hardware. This module lets you control Qontrol hardware modules, natively in Python. It provides 
a main Qontroller class which handles enumeration, low-level communications, sequencing, 
error-handling, and log maintenance. Subclasses of Qontroller implement module-specific 
features (e.g. DC current or voltage interfaces, positional interfaces).

Learn more, at www.qontrol.co.uk/support, or get in touch with us at
support@qontrol.co.uk. Contribute at www.github.com/takeqontrol/api .

## Table of contents
- Installation
- Usage
- Credits
- License


## Installation

Requirements:
- A Python 3.6 or greater interpreter.

Dependencies
- `pyserial` to enable the Serial interface communications with the Qontrollers. 

### PyPi Installation

The most stable Qontrol Python API is available through the Python Package Index PyPI. Using a bash terminal or similar, this can be installed as follows:
```bash
pip install qontrol
```

A check that the installation has been successfully performed is:

```python
>>> import qontrol
>>> qontrol.run_interactive_shell()

- - - - - - - - - - - - - -
 Qontrol Interactive Shell
- - - - - - - - - - - - - -
```



### Local Development - Github Installation

The latest development version is available through Github as instructed below.

```bash
git clone https://github.com/takeqontrol/api.git
cd api/
```

Local installation can be performed using the `setup.py` installation script.

```bash
python setup.py develop
```




## Usage
See help and documentation at https://takeqontrol.github.io/api/

## Credits
List of contributors and authors:
Qontrol
- Joshua W. Silverstone
- Raffaele Santagati
- Dario Quintero

### Contributions
If you want to contribute to this library contact support@qontrol.co.uk

## License
Copyright  &copy; 2020 Qontrol Ltd. 2020

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.





