"""
Load testing script.

Before testing, make sure to add a user account on the DistrictBuilder instance to be tested with
username and password matching the USERNAME and PASSWORD below (if you're testing a production
system you should use a secure password and change PASSWORD in this script).

Run via:

$ locust --host=http://your-district-builder-instance

Then visit http://localhost:8089 on host to run a test via the web UI.
"""
from locust import HttpLocust, TaskSet, task
from hashlib import sha1
from random import randint
import random
import string

# NOTE: Create a user with these credentials before testing
USERNAME = 'testuser'
PASSWORD = 'Test123$'

# Configuration/instance specific. Assumes PA instance.
NUM_DISTRICTS_IN_PLAN = 18
REASSIGNMENT_POST_DATA = {
    'geolevel': 2,
    'geounits': 731,
    'version': 0,
}
TEMPLATE_PLAN_ID = 2
LEGISLATIVE_BODY_ID = 1


class Static(TaskSet):
    min_wait = 1
    max_wait = 5

    @task(25)
    def get_static_asset(self):
        fragment = random.choice(self.fragments)
        self.client.get('/static/{fragment}'.format(fragment=fragment),
                        name='/static/')

    # A large number of static files tend to get requested in a row.
    @task(1)
    def stop(self):
        self.interrupt()

    fragments = [
        'css/reset.css',
        'jquery/themes/custom-theme/jquery-ui.custom.css',
        'css/core.css',
        'css/visuals.css',
        'images/icon-mail.png',
        'images/db_sprite.png',
        'jquery/jquery-1.6.2.min.js',
        'jquery/jquery-ui-1.8.16.custom.min.js',
        'jquery/external/jquery.bgiframe-2.1.1.js',
        'jquery/external/jquery.tools.tooltip.slide.min.js',
        'js/ui.js',
        'js/register.js',
        'js/sha1.js',
        'images/bg-body-home.png',
        'images/divider.png',
        'images/divider-vert.png',
        'images/bg-home-panel.png',
        'images/bg-button-lg.png',
        'jquery/themes/custom-theme/images/ui-bg_flat_75_ffffff_40x100.png',
        'images/bg-toolbar.png',
        'jquery/themes/custom-theme/images/ui-icons_222222_256x240.png',
        'jqGrid/css/ui.jqgrid.css',
        'css/redistricting.css',
        'openlayers/OpenLayers.js',
        'openlayers/ArcGISCache.js',
        'jqGrid/js/i18n/grid.locale-en.js',
        'jqGrid/js/jquery.jqGrid.min.js',
        'jqGrid/plugins/grid.postext.js',
        'js/sprintf.js',
        'js/utils.js',
        'js/viewablesorter.js',
        'js/mapping.js',
        'js/districtfile.js',
        'js/chooseplan.js',
        'js/reaggregator.js',
        'js/shareddistricts.js',
        'js/reports.js',
        'js/register.js',
        'js/statisticssets.js',
        'js/splitsreport.js',
        'js/layerchooser.js',
        'js/print.js',
        'js/multimember.js',
        'images/title-app.png',
        'images/bg-app.png',
        'images/bg-button-sm.png',
        'images/map-shadow-top.png',
        'images/map-shadow-left.png',
        'images/bg-header-panel.png',
        'images/divider-vert.png',
        'images/divider-horz.png',
        'images/bg-arrow-button.png',
        'jquery/themes/custom-theme/images/ui-icons_888888_256x240.png',
        'jquery/themes/custom-theme/images/ui-bg_highlight-soft_75_cccccc_1x100.png',
    ]


class Versioned(TaskSet):
    @task
    def get_versioned(self):
        bbox = random.choice(self.bboxes)
        self.client.get(
            '/districtmapping/plan/{plan_id}/district/versioned/'
            '?version__eq=1'
            '&queryable=version,subject,level,district_ids'
            '&subject__eq=1'
            '&bbox={bbox}'
            '&level__eq=2'
            '&district_ids__eq='.format(plan_id=self.parent.plan_id, bbox=bbox),
            name='districtmapping/plan/[plan]/district/versioned/'
        )

        self.client.get(
            '/districtmapping/plan/{plan_id}/district/versioned/'
            '?version__eq=1'
            '&queryable=version,subject,level'
            '&subject__eq=1'
            '&bbox={bbox}'
            '&level__eq=2'.format(plan_id=self.parent.plan_id, bbox=bbox),
            name='districtmapping/plan/[plan]/district/versioned/'
        )

        self.interrupt()

    bboxes = [
        '-9115495.4092665,4844142.4691214,-8681333.0886845,5039821.2614962',
        '-8939221.8809724,4915300.9109364,-8884951.5908996,4939760.7599832',
        '-8924889.7516999,4915296.4794307,-8870619.4616271,4939756.3284775',
        '-8916290.5860194,4921029.2565511,-8862020.2959466,4945489.1055979',
        '-8930622.5288203,4921029.2565511,-8876352.2387475,4945489.1055979',
        '-8936355.3059407,4920073.7936977,-8882085.0158679,4944533.6427445',
        '-8963490.4509771,4901155.6292005,-8854949.8708315,4950075.3272941',
        '-9017760.7410499,4876695.7801535,-8800679.5807587,4974535.1763411',
        '-9126301.3211953,4827776.0820599,-8692139.0006133,5023454.8744347',
        '-9343382.4814863,4729936.6858723,-8475057.8403223,5121294.2706223'
    ]


class Tiles(TaskSet):
    min_wait = 8
    max_wait = 50

    @task(45)
    def get_wms(self):
        bbox = random.choice(self.bboxes)
        self.client.get(
            '/geoserver/gwc/service/wms'
            '?SRS=EPSG%3A3857'
            '&LAYERS=pmp%3Ademo_pa_municipality_poptot'
            '&TILES=true'
            '&TILESORIGIN=-20037508.342789%2C-20037508.342789'
            '&FORMAT=image%2Fpng'
            '&TRANSPARENT=TRUE'
            '&SERVICE=WMS'
            '&VERSION=1.1.1'
            '&REQUEST=GetMap'
            '&STYLES='
            '&BBOX={bbox}'
            '&WIDTH=256'
            '&HEIGHT=256'.format(bbox=bbox),
            name='/geoserver/gwc/service/wms'
        )

    @task(1)
    def stop(self):
        self.interrupt()

    bboxes = [
        '-8883817.177414,4970241.322736,-8844681.418939,5009377.081211',
        '-8962088.694364,4970241.322736,-8922952.935889,5009377.081211',
        '-8922952.935889,4852834.047311,-8883817.177414,4891969.805786',
        '-8844681.418939,4931105.564261,-8805545.660464,4970241.322736',
        '-8883817.177414,4852834.047311,-8844681.418939,4891969.805786',
        '-8844681.418939,4891969.805786,-8805545.660464,4931105.564261',
        '-8962088.694364,4852834.047311,-8922952.935889,4891969.805786',
        '-9001224.452839,4931105.564261,-8962088.694364,4970241.322736',
        '-8844681.418939,4970241.322736,-8805545.660464,5009377.081211',
        '-9001224.452839,4891969.805786,-8962088.694364,4931105.564261',
        '-9001224.452839,4970241.322736,-8962088.694364,5009377.081211',
        '-8844681.418939,4852834.047311,-8805545.660464,4891969.805786',
        '-9001224.452839,4852834.047311,-8962088.694364,4891969.805786',
        '-8805545.660464,4931105.564261,-8766409.901989,4970241.322736',
        '-8805545.660464,4891969.805786,-8766409.901989,4931105.564261',
        '-8805545.660464,4970241.322736,-8766409.901989,5009377.081211',
        '-9040360.211314,4931105.564261,-9001224.452839,4970241.322736',
        '-9040360.211314,4891969.805786,-9001224.452839,4931105.564261',
        '-9040360.211314,4970241.322736,-9001224.452839,5009377.081211',
        '-8805545.660464,4852834.047311,-8766409.901989,4891969.805786',
        '-9040360.211314,4852834.047311,-9001224.452839,4891969.805786',
        '-8913168.9962702,4926213.5944516,-8908277.0264609,4931105.564261',
        '-8918060.9660796,4926213.5944516,-8913168.9962702,4931105.564261',
        '-8913168.9962702,4921321.6246423,-8908277.0264609,4926213.5944516',
        '-8918060.9660796,4921321.6246423,-8913168.9962702,4926213.5944516',
        '-8913168.9962702,4931105.564261,-8908277.0264609,4935997.5340704',
        '-8908277.0264609,4926213.5944516,-8903385.0566515,4931105.564261',
        '-8918060.9660796,4931105.564261,-8913168.9962702,4935997.5340704',
        '-8908277.0264609,4921321.6246423,-8903385.0566515,4926213.5944516',
        '-8922952.935889,4926213.5944516,-8918060.9660796,4931105.564261',
        '-8908277.0264609,4931105.564261,-8903385.0566515,4935997.5340704',
        '-8913168.9962702,4916429.6548329,-8908277.0264609,4921321.6246423',
        '-8922952.935889,4921321.6246423,-8918060.9660796,4926213.5944516',
        '-8918060.9660796,4916429.6548329,-8913168.9962702,4921321.6246423',
        '-8922952.935889,4931105.564261,-8918060.9660796,4935997.5340704',
        '-8908277.0264609,4916429.6548329,-8903385.0566515,4921321.6246423',
        '-8903385.0566515,4926213.5944516,-8898493.0868421,4931105.564261',
        '-8903385.0566515,4921321.6246423,-8898493.0868421,4926213.5944516',
        '-8922952.935889,4916429.6548329,-8918060.9660796,4921321.6246423',
        '-8903385.0566515,4931105.564261,-8898493.0868421,4935997.5340704',
        '-8927844.9056984,4926213.5944516,-8922952.935889,4931105.564261',
        '-8927844.9056984,4921321.6246423,-8922952.935889,4926213.5944516',
        '-8903385.0566515,4916429.6548329,-8898493.0868421,4921321.6246423',
        '-8927844.9056984,4931105.564261,-8922952.935889,4935997.5340704',
        '-8927844.9056984,4916429.6548329,-8922952.935889,4921321.6246423',
        '-8898493.0868421,4926213.5944516,-8893601.1170327,4931105.564261',
        '-8898493.0868421,4921321.6246423,-8893601.1170327,4926213.5944516',
        '-8898493.0868421,4931105.564261,-8893601.1170327,4935997.5340704',
        '-8898493.0868421,4916429.6548329,-8893601.1170327,4921321.6246423',
        '-8893601.1170327,4931105.564261,-8888709.1472233,4935997.5340704',
        '-8893601.1170327,4926213.5944516,-8888709.1472233,4931105.564261',
        '-8893601.1170327,4921321.6246423,-8888709.1472233,4926213.5944516',
        '-8893601.1170327,4916429.6548329,-8888709.1472233,4921321.6246423',
        '-8888709.1472233,4931105.564261,-8883817.1774139,4935997.5340704',
        '-8888709.1472233,4926213.5944516,-8883817.1774139,4931105.564261',
        '-8888709.1472233,4921321.6246423,-8883817.1774139,4926213.5944516',
        '-8888709.1472233,4916429.6548329,-8883817.1774139,4921321.6246423',
        '-8883817.1774139,4931105.564261,-8878925.2076045,4935997.5340704',
        '-8883817.1774139,4926213.5944516,-8878925.2076045,4931105.564261',
        '-8883817.1774139,4921321.6246423,-8878925.2076045,4926213.5944516',
        '-8883817.1774139,4916429.6548329,-8878925.2076045,4921321.6246423',
        '-8878925.2076045,4931105.564261,-8874033.2377951,4935997.5340704',
        '-8878925.2076045,4926213.5944516,-8874033.2377951,4931105.564261',
        '-8878925.2076045,4921321.6246423,-8874033.2377951,4926213.5944516',
        '-8878925.2076045,4916429.6548329,-8874033.2377951,4921321.6246423',
        '-8874033.2377951,4931105.564261,-8869141.2679857,4935997.5340704',
        '-8874033.2377951,4926213.5944516,-8869141.2679857,4931105.564261',
        '-8874033.2377951,4921321.6246423,-8869141.2679857,4926213.5944516',
        '-8874033.2377951,4916429.6548329,-8869141.2679857,4921321.6246423',
        '-8903385.0566515,4935997.5340704,-8898493.0868421,4940889.5038798',
        '-8898493.0868421,4935997.5340704,-8893601.1170327,4940889.5038798',
        '-8893601.1170327,4935997.5340704,-8888709.1472233,4940889.5038798',
        '-8888709.1472233,4935997.5340704,-8883817.1774139,4940889.5038798',
        '-8883817.1774139,4935997.5340704,-8878925.2076045,4940889.5038798',
        '-8878925.2076045,4935997.5340704,-8874033.2377951,4940889.5038798',
        '-8874033.2377951,4935997.5340704,-8869141.2679857,4940889.5038798',
        '-8908277.0264609,4935997.5340704,-8903385.0566515,4940889.5038798',
        '-8908277.0264609,4931105.564261,-8903385.0566515,4935997.5340704',
        '-8908277.0264609,4926213.5944516,-8903385.0566515,4931105.564261',
        '-8908277.0264609,4921321.6246423,-8903385.0566515,4926213.5944516',
        '-8913168.9962703,4935997.5340704,-8908277.0264609,4940889.5038798',
        '-8913168.9962703,4931105.564261,-8908277.0264609,4935997.5340704',
        '-8913168.9962703,4926213.5944516,-8908277.0264609,4931105.564261',
        '-8913168.9962703,4921321.6246423,-8908277.0264609,4926213.5944516',
        '-8918060.9660797,4935997.5340704,-8913168.9962703,4940889.5038798',
        '-8918060.9660797,4931105.564261,-8913168.9962703,4935997.5340704',
        '-8918060.9660797,4926213.5944516,-8913168.9962703,4931105.564261',
        '-8918060.9660797,4921321.6246423,-8913168.9962703,4926213.5944516',
        '-8922952.9358891,4935997.5340704,-8918060.9660797,4940889.5038798',
        '-8922952.9358891,4931105.564261,-8918060.9660797,4935997.5340704',
        '-8922952.9358891,4926213.5944516,-8918060.9660797,4931105.564261',
        '-8922952.9358891,4921321.6246423,-8918060.9660797,4926213.5944516',
        '-8922952.9358891,4916429.6548329,-8918060.9660797,4921321.6246422',
        '-8918060.9660797,4916429.6548329,-8913168.9962703,4921321.6246422',
        '-8913168.9962703,4916429.6548329,-8908277.0264609,4921321.6246422',
        '-8908277.0264609,4916429.6548329,-8903385.0566515,4921321.6246422'
    ]


class Demographics(TaskSet):
    @task
    def get_demographics(self):
        self.client.post(
            '/districtmapping/plan/{plan_id}/demographics/'.format(plan_id=self.parent.plan_id),
            {'displayId': 3, 'version': '1'},
            headers={'X-CSRFToken': self.parent.csrftoken},
            name='/districtmapping/plan/[plan]/demographics'
        )
        self.interrupt()


class UnlockedGeoms(TaskSet):
    @task(2)
    def get_unlocked_geoms(self):
        geom = random.choice(self.geoms)
        self.client.post(
            '/districtmapping/plan/{plan_id}/unlockedgeometries/'.format(
                plan_id=self.parent.plan_id
            ),
            {'bbox': '-20037508.342789,-20037508.342789,20037508.342789,20037508.342789',
             'geom__eq': geom,
             'level__eq': 2,
             'queryable': 'version,subject,level,geom',
             'subject__eq': 1,
             'version__eq': 1},
            headers={'X-CSRFToken': self.parent.csrftoken},
            name='districtmapping/plan/[plan]/unlockedgeometries/'
        )

    @task(1)
    def stop(self):
        self.interrupt()

    geoms = [
        'POLYGON((-8648312.292471 4915381.7794703,-8645254.8113402 4915381.7794703,-8645254.8113402 4918439.2606011,-8648312.292471 4918439.2606011,-8648312.292471 4915381.7794703))',
        'POLYGON((-8650146.7811495 4888475.9455187,-8647089.3000187 4888475.9455187,-8647089.3000187 4891533.4266496,-8650146.7811495 4891533.4266496,-8650146.7811495 4888475.9455187))',
        'POLYGON((-8930212.0527363 5148973.3378679,-8927154.5716054 5148973.3378679,-8927154.5716054 5152030.8189988,-8930212.0527363 5152030.8189988,-8930212.0527363 5148973.3378679))',
        'POLYGON((-8801797.8452402 5136131.9171183,-8798740.3641093 5136131.9171183,-8798740.3641093 5139189.3982492,-8801797.8452402 5139189.3982492,-8801797.8452402 5136131.9171183))',
        'POLYGON((-8658096.2320898 5126347.9774996,-8655038.7509589 5126347.9774996,-8655038.7509589 5129405.4586304,-8658096.2320898 5129405.4586304,-8658096.2320898 5126347.9774996))',
        'POLYGON((-8415332.2302995 5078651.2718582,-8412274.7491687 5078651.2718582,-8412274.7491687 5081708.752989,-8415332.2302995 5081708.752989,-8415332.2302995 5078651.2718582))',
        'POLYGON((-8492380.7547972 4978365.890766,-8489323.2736663 4978365.890766,-8489323.2736663 4981423.3718968,-8492380.7547972 4981423.3718968,-8492380.7547972 4978365.890766))',
        'POLYGON((-8409828.764264 4959409.5077546,-8406771.2831331 4959409.5077546,-8406771.2831331 4962466.9888855,-8409828.764264 4962466.9888855,-8409828.764264 4959409.5077546))',
        'POLYGON((-8366412.5322058 4904986.3436253,-8363355.0510749 4904986.3436253,-8363355.0510749 4908043.8247562,-8366412.5322058 4908043.8247562,-8366412.5322058 4904986.3436253))',
        'POLYGON((-8363355.0510749 4865239.0889242,-8360297.5699441 4865239.0889242,-8360297.5699441 4868296.570055,-8363355.0510749 4868296.570055,-8363355.0510749 4865239.0889242))',
        'POLYGON((-8370693.005789 4859735.6228886,-8367635.5246581 4859735.6228886,-8367635.5246581 4862793.1040195,-8370693.005789 4862793.1040195,-8370693.005789 4859735.6228886))',
        'POLYGON((-8372527.4944675 4860958.615341,-8369470.0133366 4860958.615341,-8369470.0133366 4864016.0964718,-8372527.4944675 4864016.0964718,-8372527.4944675 4860958.615341))',
        'POLYGON((-8382922.9303124 4848117.1945914,-8379865.4491816 4848117.1945914,-8379865.4491816 4851174.6757222,-8382922.9303124 4851174.6757222,-8382922.9303124 4848117.1945914))',
        'POLYGON((-8416555.2227519 4861570.1115671,-8413497.741621 4861570.1115671,-8413497.741621 4864627.592698,-8416555.2227519 4864627.592698,-8416555.2227519 4861570.1115671))',
        'POLYGON((-8492380.7547972 4855455.1493054,-8489323.2736663 4855455.1493054,-8489323.2736663 4858512.6304363,-8492380.7547972 4858512.6304363,-8492380.7547972 4855455.1493054))',
        'POLYGON((-8553530.3774144 4898871.3813636,-8550472.8962835 4898871.3813636,-8550472.8962835 4901928.8624945,-8553530.3774144 4901928.8624945,-8553530.3774144 4898871.3813636))',
        'POLYGON((-8645254.8113402 4861570.1115671,-8642197.3302093 4861570.1115671,-8642197.3302093 4864627.592698,-8645254.8113402 4864627.592698,-8645254.8113402 4861570.1115671))',
        'POLYGON((-8889241.8055827 4871965.5474121,-8886184.3244519 4871965.5474121,-8886184.3244519 4875023.0285429,-8889241.8055827 4875023.0285429,-8889241.8055827 4871965.5474121))',
        'POLYGON((-8900248.7376538 4923331.2304105,-8897191.256523 4923331.2304105,-8897191.256523 4926388.7115414,-8900248.7376538 4926388.7115414,-8900248.7376538 4923331.2304105))',
        'POLYGON((-8931435.0451886 4953906.0417191,-8928377.5640577 4953906.0417191,-8928377.5640577 4956963.52285,-8931435.0451886 4956963.52285,-8931435.0451886 4953906.0417191))'
    ]


class DistrictAdd(TaskSet):
    @task
    def reassign(self):
        # Reassign geounit to random district
        with self.client.post(
            '/districtmapping/plan/{plan_id}/district/{new_district}/add/'
            .format(
                plan_id=self.parent.plan_id,
                new_district=randint(1, NUM_DISTRICTS_IN_PLAN),
            ),
            REASSIGNMENT_POST_DATA,
            name='/districtmapping/plan/[plan]/district/[new_district]/add/',
            headers={'X-CSRFToken': self.parent.csrftoken},
            catch_response=True,
            allow_redirects=False
        ) as post_response:
            # NOTE: If authentication has not worked properly, you will be
            # redirected to the home page
            if post_response.status_code == 302:
                post_response.failure(
                    'User was not authenticated to perform reassignment and was redirected to login page'
                )
            else:
                if not post_response.json()['success']:
                    post_response.failure('Failed to reassign geounit')
        # Two reassignments never occur back-to-back without other types of
        # requests in between.
        self.interrupt()


class InfoClick(TaskSet):
    @task
    def get_info(self):
        search_payload = random.choice(self.search_reqs)
        detail_payload = random.choice(self.detail_reqs)
        self.client.post('/geoserver/wfs', search_payload)
        self.client.post('/geoserver/wfs', detail_payload)

        self.interrupt()

    search_reqs = [
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8662223.8316164,4926541.5855979 -8661918.0835033,4926847.333711</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8636540.9901172,4902081.736551 -8636235.2420041,4902387.4846641</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8658554.8542594,4947332.4572878 -8658249.1061463,4947638.2054008</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8645713.4335098,4919815.12711 -8645407.6853967,4920120.8752231</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8832831.2787184,5109990.4534495 -8832525.5306053,5110296.2015626</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8357087.2147567,5046394.8459276 -8356781.4666436,5046700.5940407</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8372986.1166371,4860499.9931713 -8372680.368524,4860805.7412844</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8508738.2788473,4869672.4365639 -8508432.5307342,4869978.184677</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8645713.4335098,4847658.5724217 -8645407.6853967,4847964.3205348</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8897649.8786926,4927153.0818241 -8897344.1305795,4927458.8299372</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8922721.2239656,4889240.3158014 -8922415.4758526,4889546.0639145</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">name</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">percentage</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">number</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">geolevel_id</ogc:PropertyName><ogc:PropertyName xmlns:ogc="http://www.opengis.net/ogc">subject_id</ogc:PropertyName><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:And><ogc:Intersects><ogc:PropertyName>geom</ogc:PropertyName><gml:Box xmlns:gml="http://www.opengis.net/gml" srsName="EPSG:3857"><gml:coordinates decimal="." cs="," ts=" ">-8659777.8467117,5132615.8138178 -8659472.0985987,5132921.5619309</gml:coordinates></gml:Box></ogc:Intersects><ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>geolevel_id</ogc:PropertyName><ogc:Literal>2</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo></ogc:And></ogc:Filter></wfs:Query></wfs:GetFeature>'
    ]

    detail_reqs = [
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>1194</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>1720</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>1720</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>1720</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>2068</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>1801</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>1801</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>1267</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>1046</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>116</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>2131</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>',
        '<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs" service="WFS" version="1.0.0" maxFeatures="1" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.0.0/WFS-transaction.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><wfs:Query typeName="pmp:identify_geounit" xmlns:pmp="https://github.com/PublicMapping/"><ogc:Filter xmlns:ogc="http://www.opengis.net/ogc"><ogc:PropertyIsEqualTo><ogc:PropertyName>id</ogc:PropertyName><ogc:Literal>1830</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter></wfs:Query></wfs:GetFeature>'
    ]


class RootTaskSet(TaskSet):
    tasks = {
        Static: 7,
        Versioned: 38,
        Tiles: 14,
        Demographics: 15,
        UnlockedGeoms: 14,
        DistrictAdd: 12,
        InfoClick: 9
    }

    def on_start(self):
        self.login()
        self.create_plan()
        self.get_edit_csrf()

    # Login and store cookies on client.
    def login(self):
        get_response = self.client.get('/accounts/login/')
        csrftoken = get_response.cookies['csrftoken']
        # Connection is unencrypted so the password is hashed before being sent
        # to backend.
        hashed_password = sha1(PASSWORD.encode('utf-8')).hexdigest()
        redirect_url = '/districtmapping/plan/0/view/'
        # NOTE: Cookies are stored in client object
        with self.client.post(
            '/accounts/login/', {
                'username': USERNAME,
                'password': hashed_password,
                'next': redirect_url,
            },
            headers={'X-CSRFToken': csrftoken},
            allow_redirects=False,
            catch_response=True
        ) as post_response:
            # NOTE: If authentication has not worked properly, the home page will be redelivered
            if post_response.status_code != 302:
                post_response.failure(
                    'User was not authenticated and was redirected to the home page'
                )

    # Create a plan and store the ID on self
    def create_plan(self):
        get_response = self.client.get('/districtmapping/plan/0/view/')
        post_response = self.client.post(
            '/districtmapping/plan/{template}/copy/'.format(template=TEMPLATE_PLAN_ID),
            {'legislativeBody': LEGISLATIVE_BODY_ID,
             'name': ''.join([random.choice(string.ascii_uppercase) for _ in range(8)])},
            headers={'X-CSRFToken': get_response.cookies['csrftoken']},
            catch_response=True
        )
        self.plan_id = post_response.json()[0]['pk']

    def get_edit_csrf(self):
        get_response = self.client.get(
            '/districtmapping/plan/{plan_id}/edit/'.format(plan_id=self.plan_id),
            name='districtmapping/plan/[plan]/edit/'
        )
        self.csrftoken = get_response.cookies['csrftoken']


class ApplicationUser(HttpLocust):
    task_set = RootTaskSet
    min_wait = 200
    max_wait = 3000
