
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
                $(this).button({icons: {primary: 'ui-icon-arrow-down'}})
              })
            .click(function(){
              if ( $(".map_menu_content:visible'").length === 0) {
                 $storedPanel.slideDown(200);
              } else {
              $('.map_menu_content:visible').each(function() {
                  $storedPanel = $(this);
                  $(this).slideUp(200);
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

            
 
	});
