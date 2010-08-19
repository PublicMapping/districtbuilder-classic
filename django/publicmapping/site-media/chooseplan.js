
var publicmapping = {};

publicmapping.chooseplan = function(options) {

    var _self = {},
        _options = $.extend({
            target: {},
            container: {},
            callback: function() {},
            autoOpen: false,
            modal: true,
            width: 600,
            resizable: false
        }, options),
        // bunch o variables
       
        _eventType,
        _nameRequired,
        _dialog;

    _self.init = function() {
        _options.container.load('/districtmapping/plan/choose/', function() {
            setUpTarget(); 
            setUpEvents(); 
            _options.callback(); 
        });
        
        _nameRequired = false;
        
        return _self;
    };
    var setUpTarget = function() {
        $('#PlanChooser').dialog(_options);
        _options.target.click( function() {
            $('#PlanChooser').dialog('open');
            loadButtons();
        });
    };


    var setUpEvents = function() {
        $('.Selectors').hide();
        $('.SelectionGroup').hide();
        $('#SelectorHelp').show();
        $('#btnBlank').click(function() { 
            _eventType = 'blank'; 
            showOnly('#BlankSelection', '#btnBlank'); 
        });
        $('#btnTemplate').click(function() { 
            _eventType = 'template'; 
            showOnly('#TemplateSelection','#btnTemplate'); 
        });
        $('#btnShared').click(function() { 
            _eventType = 'shared'; 
            showOnly('#SharedSelection','#btnShared'); 
        });
        $('#btnMine').click(function() { 
            _eventType = 'mine'; 
            showOnly('#MineSelection','#btnMine');
        });
        $('#btnSelectPlan').click(selectPlan);
        $('#NewName').hide();
        $('input:radio').click( function() {
            if ($(this).val() == 'edit') {
                $('#NewName').hide(); 
                _nameRequired = false;
            } else {
                $('#NewName').show();
                _nameRequired = true;
            }
        });
    };

    var showOnly = function(selectorId,buttonID) {
        $('#TemplateTypeButtons li').removeClass('active');
        $(buttonID).addClass('active');
        
        $('#SelectorsHelp').hide();
        $('.SelectionGroup').hide();
        $('.Selectors').removeClass('active');
        $(selectorId).show();
        var selectors = $(selectorId + ' .Selectors'); 
        selectors.show().addClass('active');
        if ( selectors.length > 0 && selectors[0].nodeName != 'SELECT' ) {
            $('#btnSelectPlan').hide();
        }
        else {
            $('#btnSelectPlan').show();
        }
        if (_eventType == 'blank' || _eventType == 'template' || 
            ( selectorId == '#MineSelection' && $('input:radio:checked').val() == 'saveas'  )) {
            $('#NewName').show();
            _nameRequired = true;
        } else {
            _nameRequired = false;
            $('#NewName').hide();
        }
    };

    var selectPlan = function () {
        $('#btnSelectPlan').attr('disabled','true');
        var activeText = $('#btnSelectPlan span').text();
        $('#btnSelectPlan span').text('Please Wait...');
        var activeSelector = $('select.active');
        if (_nameRequired) {
            var name = $('#txtNewName').val();
            var url = '/districtmapping/plan/' + activeSelector.val() + '/copy/';
            if (_eventType == 'blank') {
                url = '/districtmapping/plan/create/';
            }

            if (name.trim().length == 0) { 
                alert ('A name for the copied template is required'); 
                $('#btnSelectPlan').attr('disabled',null);
                $('#btnSelectPlan span').text(activeText);
                return; 
            }
            if (OpenLayers) {
                OpenLayers.Element.addClass(document.getElementById('btnSelectPlan'),'olCursorWait');
                OpenLayers.Element.addClass(document.body,'olCursorWait');
            }
            window.status = 'Please standby while creating new plan ...';
            $.post(url, { name: $('#txtNewName').val() }, copyCallback, 'json');
        }
        else if ( _eventType == 'mine' ) {
            window.location = '/districtmapping/plan/' + activeSelector.val() + '/edit/';
        }
        else {
            window.location = '/districtmapping/plan/' + activeSelector.val() + '/view/';
        }
    };

    var copyCallback = function(data) {
        data = data[0];
        if (data.pk) {
            window.location = '/districtmapping/plan/' + data.pk + '/edit/';
        } else {
            alert (data.message);
        }
    };

    return _self;
};

