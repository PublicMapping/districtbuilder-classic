## Utilities for Redis - mostly just a function for generating keys ##


def key_gen(**kwargs):
    """
    Key generator for linux. Determines key based on
    parameters supplied in kwargs.

    Keyword Parameters:
    @keyword geounit1: portable_id of a geounit
    @keyword geounit2: portable_id of a geounit
    @keyword region: region abbreviation
    """
    if 'geounit1' in kwargs and 'geounit2' in kwargs:
        return 'adj:geounit1:%s:geounit2:%s' % (kwargs['geounit1'],
                                                kwargs['geounit2'])

    if 'region' in kwargs:
        return 'adj:region:%s' % kwargs['region']
