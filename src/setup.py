from setuptools import setup
import setup_translate

pkg = 'Extensions.FanControl2'
setup(name='enigma2-plugin-extensions-fancontrol2',
       version='3.0',
       description='Temperature dependent fan control',
       package_dir={pkg: 'FanControl2'},
       packages=[pkg],
       package_data={pkg: ['images/*.png', '*.png', '*.xml', 'locale/*/LC_MESSAGES/*.mo', 'plugin.png', '*.txt', 'maintainer.info', 'LICENSE', 'data/*.png', 'data/diagram.class.org']},
       cmdclass=setup_translate.cmdclass,  # for translation
      )
