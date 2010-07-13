/*
 * Create an OpenLayers.Layer.WMS type layer.
 *
 * @param name The name of the layer (appears in the layer switcher).
 * @param layer The layer name (or array of names) served by the WMS server.
 * @param extents The extents of the layer -- must be used for GeoWebCache.
 */
function createLayer( name, layer, extents ) {
    return new OpenLayers.Layer.WMS( name,
        'http://' + MAP_SERVER + '/geoserver/gwc/service/wms',
        { srs: 'EPSG:3785',
          layers: layer,
          tiles: 'true',
          tilesOrigin: extents.left + ',' + extents.bottom,
          format: 'image/png'
        },
	{
	  displayOutsideMaxExtent: true
	}
    );
}

/*
 * Resize the map. This is a fix for IE, which does not assign a height
 * to the map div if it is not explicitly set.
 */
function resizemap() {
    var mapElem = document.getElementById('mapandmenu');
    if(!window.innerHeight) {
        mapElem.style.height = (window.document.body.clientHeight - 76) + 'px';
    }
    else {
        mapElem.style.height = (window.innerHeight - 79) + 'px';
    }
}

/*
 * Initialize the map. This method is called by the onload page event.
 */
function init() {
    OpenLayers.ProxyHost= "/proxy?url=";

    // set up sizing for dynamic map size that fills the pg
    resizemap();
    window.onresize = resizemap;

    // The extents of the layers. These extents will depend on the study
    // area; the following are the bounds for the web cache around Ohio.
    // TODO Make the initial layer extents configurable. Maybe fetch them
    // from geowebcache
    var layerExtent = new OpenLayers.Bounds(
        -9442154.0,
        4636574.5,
        -8868618.0,
        5210110.5
    );

    // This projection is web mercator
    var projection = new OpenLayers.Projection('EPSG:3785');

    // Create a slippy map.
    var olmap = new OpenLayers.Map('map', {
        // The resolutions here must match the settings in geowebcache.
        // TODO Fetch these resolutions from geowebcache
        resolutions: [2240.375, 1120.1875, 560.09375,
            280.046875, 140.0234375, 70.01171875,
            35.005859375, 17.5029296875, 8.75146484375,
            4.375732421875, 2.1878662109375, 1.09393310546875,
            0.546966552734375, 0.2734832763671875, 0.13674163818359375,
            0.06837081909179688, 0.03418540954589844,
            0.01709270477294922, 0.00854635238647461, 0.004273176193237305,
            0.0021365880966186523, 0.0010682940483093262,
            5.341470241546631E-4, 2.6707351207733154E-4, 1.3353675603866577E-4],
        maxExtent: layerExtent,
        projection: projection,
        units: 'm'
    });

    // These layers are dependent on the layers available in geowebcache
    // TODO Fetch a list of layers from geowebcache
    var layers = [];
    for (layer in MAP_LAYERS) {
        layers.push(createLayer( MAP_LAYERS[layer], MAP_LAYERS[layer], layerExtent ));
    }

    var match = window.location.href.match(new RegExp('/plan\/(\\d+)\/edit/'));
    var plan_id = match[1];
    var districtStrategy = new OpenLayers.Strategy.Refresh({force:true});
    
    var districtLayer = new OpenLayers.Layer.Vector(
        'Current Plan',
        {
            strategies: [
                new OpenLayers.Strategy.BBOX(), districtStrategy
            ],
            protocol: new OpenLayers.Protocol.WFS({
                url: 'http://' + MAP_SERVER + '/geoserver/wfs',
                featureType: 'simple_district',
                featureNS: 'http://gmu.azavea.com/',
                featurePrefix: 'gmu',
                geometryName: 'geom',
                srsName: 'EPSG:3785'
            }),
            styleMap: new OpenLayers.StyleMap({
                fill: false,
                strokeColor: '#ee9900',
                strokeOpacity: 1,
                strokeWidth: 2
            }),
            projection:projection,
            filter: new OpenLayers.Filter.Comparison({
                type: OpenLayers.Filter.Comparison.EQUAL_TO,
                property: 'plan_id',
                value: plan_id
            })
        }
    );
/*
    var districtLayer = new OpenLayers.Layer.WMS(
        'Current Plan',
        'http://' + MAP_SERVER + '/geoserver/wms',
        { srs: 'EPSG:3785',
          layers: 'gmu:gmu_plan',
          format: 'image/png',
          cql_Filter: 'plan_id=1'  
        },
        {
            singleTile: true,
            buffer: 0,
            projection: projection,
            isBaseLayer: false,
            opacity: 0.5
        }
    );
*/

    var selection = new OpenLayers.Layer.Vector('Selection',{
        styleMap: new OpenLayers.StyleMap({
            fill: false,
            strokeColor: '#ffff00',
            strokeOpacity: 0.75,
            strokeWidth: 3
        })
    });

    layers.push(districtLayer);
    layers.push(selection);
    olmap.addLayers(layers);

    var getControl = new OpenLayers.Control.GetFeature({
        protocol: new OpenLayers.Protocol.WFS({
            url: 'http://' + MAP_SERVER + '/geoserver/wfs',
            featureType: 'county',
            featureNS: 'http://gmu.azavea.com/',
            featurePrefix: 'gmu',
            srsName: 'EPSG:3785',
            geometryName: 'geom'
        })
    });

    getControl.events.register('featureselected', this, function(e){
        selection.addFeatures([e.feature]);
    });
    getControl.events.register('featureunselected', this, function(e){
        selection.removeFeatures([e.feature]);
    });

    var assignControl = new DistrictAssignment({
        selection: selection,
        districts: districtLayer
    });

    var jsonParser = new OpenLayers.Format.JSON();

    assignControl.events.register('geounitadded', this, function(e){
        var district_id = e.district;
        var feature = e.selection[0];
        OpenLayers.Request.POST({
            method: 'POST',
            url: '/districtmapping/plan/' + plan_id + '/district/' + district_id + '/add',
            params: {
                geolevel: feature.attributes.geolevel_id,
                geounits: feature.attributes.id
            },
            success: function(xhr) {
                var data = jsonParser.read(xhr.responseText);
                if (data.success) {
                    districtStrategy.refresh();
                    selection.removeFeatures(selection.features);
                }
            },
            failure: function(xhr) {
                assignControl.reset();
            }
        });
    });

    olmap.events.register('changelayer', getControl, function(e){
        if ( e.layer.isBaseLayer && e.layer[e.property]) {
            var newOpts = getControl.protocol.options;
            newOpts.featureType = e.layer.name.substring( getControl.protocol.featurePrefix.length + 1 );
            getControl.protocol = new OpenLayers.Protocol.WFS( newOpts );
        }
    });

    olmap.addControls([
        new OpenLayers.Control.LayerSwitcher(),
        getControl,
        assignControl
    ]);

    getControl.activate();

    // Set the initial map extents to the bounds around the study area.
    // TODO Make these configurable.
    olmap.zoomToExtent(new OpenLayers.Bounds(-9467000,4570000,-8930000,5170000));
}

/************************************************************************/
/* DistrictAssignment
/* A control for assigning a district after it's been selected.
/***********************************************************************/
/** 
 * @requires OpenLayers/Control.js
 */

/**
 * Class: DistrictAssignment
 * The DistrictAssignment control shows a drop-down of available districts
 * that can accept the currently selected district. This control appears
 * in the upper right of the map automatically when a feature is selected.
 * 
 * Inherits from:
 *  - <OpenLayers.Control>
 */
DistrictAssignment = 
  OpenLayers.Class(OpenLayers.Control, { 
    /**
     * Constant: EVENT_TYPES
     *
     * Supported event types:
     *  - *geounitadded* Triggered when a geounit is added.
     */
    EVENT_TYPES: ["geounitadded"],

    /**
     * Property: selectionLayer
     * The layer that contains the selection features and fires pick events.
     */
    selectionLayer: null,

    /**
     * Property: districtLayer
     * The layer that contains the districts that have already been mapped.
     */
    districtLayer: null,
 
  // DOM Elements
    
    /** 
     * Property: controlDiv
     * {DOMElement}
     */
    controlDiv: null,

    /**
     * Property: selectElem
     * {DOMElement}
     */
    selectElem: null,
    
    /**
     * Constructor: DistrictAssignment
     * 
     * Parameters:
     * options - {Object}
     */
    initialize: function(options) {
        this.EVENT_TYPES = 
            DistrictAssignment.prototype.EVENT_TYPES.concat(
            OpenLayers.Control.prototype.EVENT_TYPES
        );
        OpenLayers.Control.prototype.initialize.apply(this, arguments);
        this.selectionLayer = options.selection;
        this.districtLayer = options.districts;

        if (this.selectionLayer) {
          this.selectionLayer.events.on({
              "featureadded": this.showList,
              "featureremoved": this.hideList,
              scope: this
          });
        }
    },

    /**
     * APIMethod: destroy 
     */    
    destroy: function() {
        
        OpenLayers.Event.stopObservingElement(this.div);
        OpenLayers.Event.stopObservingElement(this.controlDiv);
        
        this.selectionLayer.events.un({
            "featureadded": this.showList,
            "featureremoved": this.hideList,
            scope: this
        });
        
        OpenLayers.Control.prototype.destroy.apply(this, arguments);
    },

    showList: function(feat) {
        this.controlDiv.style.display = 'block';
        this.selectElem.selectedIndex = 0;
        this.selectElem.options.length = 2;
        for (var i = 0; i < this.districtLayer.features.length; i++) {
            var dFeat = this.districtLayer.features[i];
            if (dFeat.geometry.intersects &&
                dFeat.geometry.intersects(feat.feature.geometry)) {
                this.selectElem.options[this.selectElem.options.length] =
                    new Option( dFeat.attributes.name, dFeat.attributes.district_id );
            }
        }
    },

    hideList: function(feat) {
        this.controlDiv.style.display = 'none';
    },

    /** 
     * Method: setMap
     *
     * Properties:
     * map - {<OpenLayers.Map>} 
     */
    setMap: function(map) {
        OpenLayers.Control.prototype.setMap.apply(this, arguments);
    },

    /**
     * Method: onDistrictSelect
     *
     * Parameters:
     * e - {Event}
     *
     * Context:
     *  - {DOMElement} selectElem
     *  - {<OpenLayers.Layer>} selectionLayer
     *  - {DistrictAssignment} districtAssigner
     */
    onDistrictSelect: function(e) {
        if (this.selectElem.selectedIndex > 0) {
            this.districtAssigner.events.triggerEvent('geounitadded', {
                selection: this.selectionLayer.features,
                district: this.selectElem.value
            });
        }
    },

    /**
     * Method: reset
     * Reset the selection box after a district has been assigned.
     */
    reset: function() {
        this.selectElem.selectedIndex = 0;
    }, 

    /**
     * Method: draw
     *
     * Returns:
     * {DOMElement} A reference to the DIV DOMElement containing the 
     *     switcher tabs.
     */  
    draw: function() {
        OpenLayers.Control.prototype.draw.apply(this);

        this.loadContents();

        // populate div with current info
        this.redraw();    

        return this.div;
    },
    
    /** 
     * Method: redraw
     * Goes through and takes the current state of the Map and rebuilds the
     *     control to display that state. Groups base layers into a 
     *     radio-button group and lists each data layer with a checkbox.
     *
     * Returns: 
     * {DOMElement} A reference to the DIV DOMElement containing the control
     */  
    redraw: function() {
        // create input element
        this.selectElem = document.createElement("select");
        this.selectElem.id = this.id + "_select";
        this.selectElem.name = this.id + "_select";
        this.selectElem.options[0] = new Option('-- Select One --');
        this.selectElem.options[1] = new Option('Unassigned','0');

        var context = {
            'selectElem': this.selectElem,
            'selectionLayer': this.selectionLayer,
            'districtAssigner': this
        };
        OpenLayers.Event.observe(this.selectElem, "change", 
            OpenLayers.Function.bindAsEventListener(this.onDistrictSelect,
                                                    context)
        );
                
        // create span
        var labelSpan = document.createElement("span");
        OpenLayers.Element.addClass(labelSpan, "labelSpan")
        
        labelSpan.innerHTML = 'Assign to District';
        labelSpan.style.verticalAlign = "bottom";
        OpenLayers.Event.observe(labelSpan, "click", 
            OpenLayers.Function.bindAsEventListener(this.onDistrictSelect,
                                                    context)
        );
        
        this.controlDiv.appendChild(labelSpan);
        this.controlDiv.appendChild(this.selectElem);
        this.controlDiv.style.display = 'none';

        this.div.style.right = '0';
        this.div.style.top = '0';
        return this.div;
    },

    /**
     * Method: showControls
     * Hide/Show all LayerSwitcher controls depending on whether we are
     *     minimized or not
     * 
     * Parameters:
     * minimize - {Boolean}
     */
    showControls: function(minimize) {

        this.maximizeDiv.style.display = minimize ? "" : "none";
        this.minimizeDiv.style.display = minimize ? "none" : "";

        this.controlDiv.style.display = minimize ? "none" : "";
    },
    
    /** 
     * Method: loadContents
     * Set up the labels and divs for the control
     */
    loadContents: function() {

        //configure main div

        OpenLayers.Event.observe(this.div, "mouseup", 
            OpenLayers.Function.bindAsEventListener(this.mouseUp, this));
        OpenLayers.Event.observe(this.div, "click",
                      this.ignoreEvent);
        OpenLayers.Event.observe(this.div, "mousedown",
            OpenLayers.Function.bindAsEventListener(this.mouseDown, this));
        OpenLayers.Event.observe(this.div, "dblclick", this.ignoreEvent);

        // layers list div        
        this.controlDiv = document.createElement("div");
        this.controlDiv.id = this.id + "_controlDiv";
        OpenLayers.Element.addClass(this.controlDiv, "controlDiv");

        this.div.appendChild(this.controlDiv);
    },
    
    /** 
     * Method: ignoreEvent
     * 
     * Parameters:
     * evt - {Event} 
     */
    ignoreEvent: function(evt) {
        OpenLayers.Event.stop(evt);
    },

    /** 
     * Method: mouseDown
     * Register a local 'mouseDown' flag so that we'll know whether or not
     *     to ignore a mouseUp event
     * 
     * Parameters:
     * evt - {Event}
     */
    mouseDown: function(evt) {
        this.isMouseDown = true;
        this.ignoreEvent(evt);
    },

    /** 
     * Method: mouseUp
     * If the 'isMouseDown' flag has been set, that means that the drag was 
     *     started from within the LayerSwitcher control, and thus we can 
     *     ignore the mouseup. Otherwise, let the Event continue.
     *  
     * Parameters:
     * evt - {Event} 
     */
    mouseUp: function(evt) {
        if (this.isMouseDown) {
            this.isMouseDown = false;
            this.ignoreEvent(evt);
        }
    },

    CLASS_NAME: "DistrictAssignment"
});

