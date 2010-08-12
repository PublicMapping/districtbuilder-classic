function loadButtons() {
    $('button, input[button]').button();
}

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
      
     $("#stats_legend").tooltip({
       position: 'top center',
       effect: 'slide',
       delay: 200,
       offset: [10,0],
       opacity: .8,
             onBeforeShow:  function() {
          // ensure proper DOM placement
          this.getTip().appendTo('body');
          },
      onHide:  function() {
          // restore original DOM placement
          this.getTip().appendTo(this.getTrigger());
          }
     })  
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
              } else {
              $('.map_menu_content:visible').each(function() {
                  $storedPanel = $(this);
                  $storedPanel.slideUp(200);
                });
              }  
              });
        
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
            } else {
              $('.toolset').each(function(){
                $(this).addClass('active').animate({marginTop: '-=51'}, 200)
               })
            }
         });

        $('#saveplaninfo').bind('planSaved', function(event, time) {
            var date = new Date(time);
            var hours = date.getHours();
            var minutes = date.getMinutes();
            $('#saveplaninfo').text('Last Saved at ' + hours + ':' + ((minutes < 10) ? ('0' + minutes) : minutes));
        });

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
/*
        $('#saveplanbtn').click(function(){
            $('#working').dialog('open');

            $.ajax({
                url: '/districtmapping/plan/' + PLAN_ID,
                type: 'POST',
                success: function(data, textStatus, xhr) {
                    $('#working').dialog('close');
                    if (data.success) {
                        $('#saveplaninfo').trigger('planSaved', new Date().valueOf());
                    }
                    else {
                        // how to notify that the plan was not saved?
                        window.status = data.message;
                    }
                }
            });
        });
*/
    });
