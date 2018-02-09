from distutils.core import setup

setup(
    name="district_builder_config",
    version="0.1.0",
    packages=["district_builder_config"],
    package_data={'': ['templates/*.j2']},
    install_requires=[
        'jinja2',
        'lxml',
    ],
)
