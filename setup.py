import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()
setuptools.setup(
     name='qontrol',  
     version='0.0.1',
     scripts=['qontrol_echo'],
     py_modules=["qontrol"],
     author="Qontrol",
     author_email="hello@qontrol.co.uk",
     install_requires=['pyserial'],
     description="Qontrol python API",
     long_description=long_description,
   long_description_content_type="text/markdown",
     url="https://github.com/takeqontrol/qontrol_api",
     packages=setuptools.find_packages(),
     classifiers=[
         "Programming Language :: Python :: 3",
         "License :: OSI Approved :: MIT License",
         "Operating System :: OS Independent",
     ],
     python_requires='>=3.6',
 )