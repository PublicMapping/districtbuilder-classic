reports = function(options) {

    var _self = {},
        _options = $.extend({
            previewContainer: $('#reportPreview'),
            trigger: $('#btnViewReport'),
            reportUrl: '',
            callback: function() {},
        }, options),
        _popVar,
        _popVarExtra,
        _ratioVars,
        _splitVars,
        _blockLabelVar,
        _repCompactness,
        _repCompactnessExtra,
        _repSpatial,
        _repSpatialExtra;

    _self.init = function() {
        _options.trigger.click( function() {
            submitReportRequestToServer();
            _options.callback(); 
        });
        return _self;
    };
    
    var submitReportRequestToServer = function() {
        data = getReportOptions();
        $.post(_options.reportUrl, data, loadPreviewContent);
    };

    var getReportOptions = function() {
        var data = { _popVar: 'POPTOT' };
        return data;
    };

    var loadPreviewContent = function(data, textStatus, XMLHttpRequest) {
        if (data.success) {
            _options.previewContainer.html(data.preview); 
        } 
        else {
            $('<div title="Report Error>Sorry, we weren\'t able to preview this report; <p>' + data.message + '</p></div>').dialog({ autoOpen:true });
        }
    };

    return _self;
};
