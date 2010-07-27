publishplan = function(options) {

    var _self = {},
        _options = $.extend({
            target: {},
            container: {},
            callback: function() {},
            autoOpen: false,
            modal: true,
            width:600,
        }, options),
        // bunch o variables
        
        _nameRequired,
        _editType,
        _selectionType,
        _dialog;

    _self.init = function() {
        _options.container.load('/districtmapping/plan/' + PLAN_ID + '/publish/', function() { setUpTarget(); setUpEvents(); _options.callback(); })
        
        return _self;
    };
    var setUpTarget = function() {
        $('#PlanPublisher').dialog(_options);
        _options.target.click( function() {
            $('#PlanPublisher').dialog('open');
            loadButtons();
        });
    };


    var setUpEvents = function() {
        $('#btnPublishPlan').click( function() {
            notImplemented();
        });

        $('#btnSubmitPlan').click( function() {
            notImplemented();
        });

        $('#btnClose').click(_close);

        
        var notImplemented = function() {
            $('<div class="error" title="Sorry">This feature has not yet been implemented. Stay tuned.</div>)').dialog({
                autoOpen:true,
                modal:true,
            });
        };

    };

    var _close = function() {
        $('#PlanPublisher').dialog('close');
    };

    return _self;
};

