
var publicmapping = {};

publicmapping.chooseplan = function(options) {

    var _self = {},
        _options = $.extend({
            // my defaults here
        }, options),
        // bunch o variables
        
        _nameRequired,
        _editType,
        _selectionType;

    _self.init = function() {
        $('.Selectors').hide();
        $('.SelectionGroup').hide();
        $('#SelectorHelp').show();
        $('#btnBlank').click(function() { window.location = '/districtmapping/plan/create'; });
        $('#btnTemplate').click(function() { showOnly('#TemplateSelection'); });
        $('#btnShared').click(function() { showOnly('#SharedSelection'); });
        $('#btnMine').click(function() { showOnly('#MineSelection'); });
        $('#btnSelectPlan').click(function() { selectPlan(); });
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

        _nameRequired = false;

        return _self;
    };

    var showOnly = function(selectorId) {
        $('#SelectorsHelp').hide();
        $('.SelectionGroup').hide();
        $('.Selectors').removeClass('active');
        $(selectorId).show();
        $(selectorId + ' .Selectors').show().addClass('active');
        if (selectorId == '#TemplateSelection' || selectorId == '#SharedSelection' ||
            ( selectorId == '#MineSelection' && $('input:radio:checked').val() == 'saveas'  )) {
            $('#NewName').show();
            _nameRequired = true;
        } else {
            _nameRequired = false;
            $('#NewName').hide();
        }
    };

    var selectPlan = function () {
        var activeSelector = $('.active');
        if (_nameRequired) {
            var name = $('#txtNewName').val();
            var url = '/districtmapping/plan/' + activeSelector.val() + '/copy/'
            if (name.trim().length == 0) { alert ('A name for the copied template is required'); return; }
            $.post(url, { name: $('#txtNewName').val() }, copyCallback, 'json');
        }
        else {
            window.location = '/districtmapping/plan/' + activeSelector.val() + '/edit/';
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

