/*
   Copyright 2010 Micah Altman, Michael McDonald

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

   This file is part of The Public Mapping Project
   http://sourceforge.net/projects/publicmapping/

   Purpose:
       This script file contains utility funtions that are used throughout
       the user interface for button and dialogs and tooltips.

   Author: 
        Andrew Jennings, David Zwarg
*/

/**
 * Configure all buttons to look and behave like jQuery buttons.
 */
function loadButtons() {
    $('button, input[button]').button();
}

/**
 * Configure all tooltips. This function configures tags with the class
 * "divtip", "titletip", as well as the stats legend.
 */
function loadTooltips() {
    $(".divtip").tooltip({ 
        position: 'bottom left',
        offset: [8,10],
        delay: 200,
        predelay: 50,
        opacity: .8,      
        onBeforeShow:  function() {
            // ensure proper DOM placement
            this.getTip().appendTo('body');
        },
        onHide:  function() {
            // restore original DOM placement
            this.getTip().appendTo(this.getTrigger());
        }
    });    
  
    $(".titletip[title]").tooltip({
        position: 'bottom right',
        delay: 250,
        predelay: 600,
        opacity: .8
    });    
      
    // If the user left the stats_legend_panel up when it's refreshed, it may be
    // attached to the body rather than appended to the trigger.
    $('body > #stats_legend_panel').remove();

    // This shows the legend when the trigger is clicked
    $("#stats_legend").tooltip({
        position: 'top center',
        effect: 'slide',
        delay: 200,
        offset: [10,0],
        opacity: .8,
        events: {
            widget: 'click,click'
        },
        onBeforeShow:  function() {
            // ensure proper DOM placement
            this.getTip().appendTo('body');
            // close on the next trigger click - putting this here as a "one()"
            // method keeps the handlers from piling up as the tabs are refreshed.
            $('#stats_legend').one('click', function() {
                var tip = $('#stats_legend').tooltip();
                if (tip.isShown(true)) {
                    tip.hide();
                }
                return false;
            });
        },
        onHide:  function() {
            // restore original DOM placement
            this.getTip().appendTo(this.getTrigger());
        }
    });  
}

/**
 * Configure the tooltips and buttons
 */
// Given a UTC time in ISO format, translate to browser local time
function getLocalTimeFromIsoformat(time) {
    var dashRE = new RegExp('\-','g');
    var milliRE = new RegExp('\.\\d*$');
    var tzRE = new RegExp('T');
    var date = new Date(time);
    if (isNaN(date)) {
        // additional text wrangling for IE
        time = time.replace(dashRE,'\/')
            .replace(milliRE,'')
            .replace(tzRE, ' ');
        date = new Date(time);
    }
    // get the time zone offset in minutes, then multiply to get milliseconds
    var offset = date.getTimezoneOffset() * 60000;
    date = new Date(date - offset);
    var hours = date.getHours() ;
    var minutes = date.getMinutes();
    var day = date.getMonth() + "/" + date.getDate();
    return { hours: hours, minutes: minutes, day: day };
}

$(function() {
    // jQuery-UI tab layout
    $('#steps').tabs();
    
    // jQuery Tools tooltips   
    loadTooltips();
    
    // jQuery-UI buttons   
    loadButtons();
    
    // stats dropdown button
    $('.menu_toggle')
        .button({
            icons: {primary: 'ui-icon-arrow-down'},text: false})
        .toggle(
            function(){
                $(this).button({icons: {primary: 'ui-icon-arrow-right'}})
            },
            function(){
                $(this).button({icons: {primary: 'ui-icon-arrow-down'}});
            })
        .click(function(){
            if ( $(".map_menu_content:visible'").length === 0) {
                $storedPanel.slideDown(200);
            }
            else {
                $('.map_menu_content:visible').each(function() {
                    $storedPanel = $(this);
                    $storedPanel.slideUp(200);
                });
            }  
        });
    
    // the menu type selector dropdown
    $("#map_menu_header select").change(function(){
        var selectedVal = this.value;
        $('.map_menu_content').each(function() {       
          if($(this).hasClass(selectedVal)) {
              $(this).slideDown(200);
          }
          else {
              $(this).slideUp(200);
          }
        });  
    }).val("demographics").attr("selected", "selected");
        
        $("#map_menu_header select").change(function(){
            var selectedVal = this.value;
            $('.map_menu_content').each(function() {       
              if($(this).hasClass(selectedVal)) {
                  $(this).slideDown(200);
              }
              else {
                  $(this).slideUp(200);
              }
            });  
        }).val("demographics").attr("selected", "selected");
        
        
        $('#snapto').change( function() {
            $('#showby').siblings('label').text('Show ' + $('#snapto option:selected').text() + ' by:');

        });

        // map editing buttons
        $('#toolset_draw .toolset_group button')
          .button({
              icons: {primary: 'ui-icon'},
              text:false
          })
          .click(function(){
            if($(this).hasClass('btntoggle')) {
                $('.toolset_group button.btntoggle').removeClass('toggle');
                $(this).addClass('toggle');
            }
        });    
        
    //toolset toggle button
    $('.toolbar_toggle').click(function(){
        if($('.toolset').hasClass('active')) {
            $('.toolset').each(function() {
                $(this).removeClass('active').animate({marginTop: '+=51'}, 200)
            });
        }
        else {
            $('.toolset').each(function(){
                $(this).addClass('active').animate({marginTop: '-=51'}, 200)
            })
        }
    });

        $('#saveplaninfo').bind('planSaved', function(event, time) {
            var local = getLocalTimeFromIsoformat(time);
            $('#saveplaninfo').text('Last Saved at ' + (local.hours % 12) + ':' + ((local.minutes < 10) ? ('0' + local.minutes) : local.minutes));
        });


        try {
            var saved = $('#saveplaninfo').text().trim();
            var local = getLocalTimeFromIsoformat(saved);
            $('#saveplaninfo').text('Plan saved ' + local.day + ' at ' + (local.hours % 12) + ':' + ((local.minutes < 10) ? ('0' + local.minutes) : local.minutes));
        } catch (error) {
           // Just leave it: "no plan selected"
        }

        $('#map_legend').click(function(){
            var toggle = $(this);
            var panel = $('#map_legend_content');
            if(toggle.hasClass('active')) {
                toggle.removeClass('active');
                panel.slideUp(240);
            }
            else {
                toggle.addClass('active');
                panel.slideDown(240);
            }
        });
        
    // report category parents toggling
    $('#reportdescription .master input').click( function() {
        $this = $(this);
        var id = $this.attr('id');
        var category = id.substring(0, id.indexOf('_'));
        var checked = $this.attr('checked');
        $('#reportdescription .' + category + ' input').attr('checked', $this.attr('checked'));     
    });
    $('#reportdescription .reportVar input').click( function() {
        $this = $(this).closest('span');
        var id = $this.attr('id');
        var categories = $this.attr('class');
        var category = categories.split(' ')[0]; 
        if ($this.find('input').attr('checked') == false) {
            $('#' + category + '_master').attr('checked', false);     
        }
    });

    /* The Save and Share button.  */
    $('#btnSaveAndShare').click( function() { 
        // Helper function to get name for shared plan
        var getData = function() {
            var name = $('#txtPlanName').val();
            if (name == '') { return false; }
            return { name: name, shared: true }; 
        };
        // The dialog to display while contacting the server.  Shouldn't be closable
        var $waitPublishing = $('<div title="Please Wait">Publishing with the server</div>').dialog({ autoOpen: true, escapeOnClose: false, resizable:false, open: function(event, ui) { $(".ui-dialog-titlebar-close", $(this).parent()).hide(); } });
        var data = getData();
        if (!data) {
            $waitPublishing.dialog('close');
            $('<div title="Error">Please enter a new name to publish your plan</div>').dialog({ autoOpen: true });
            return false;
        }
        else {
            $.ajax({
                url: '/districtmapping/plan/' + PLAN_ID + '/copy/',
                type: 'POST',
                data: data,
                success: function(data, textStatus, xhr) {
                    $waitPublishing.dialog('close');
                    if (('success' in data) && !data.success) {
                        $waitPublishing.dialog('close');
                        $('<div title="Oops!">' + data.message + '</div>').dialog({autoOpen:true});
                    }
                    else if (textStatus == 'success') {
                        var link ='http://' + location.host + '/districtmapping/plan/' + data[0].pk + '/view/' 
                        $('#sharedPermalink').html('<a href="' + link + '">' + link + '</a>')
                        $('#continueEditing').click( function() {
                            $('#successfulShare').dialog('close');
                            $('#steps').tabs('select', '#step-1');
                        });
                        $('#successfulShare').dialog({autoOpen: true});
                    }
                },
                error: function() {
                    $waitPublishing.dialog('close');
                    $('<div title="Server Failure">Sorry, we weren\'t able to contact the server.  Please try again later.</div>').dialog({autoOpen:true});
                }
            });
        }
    });
});
