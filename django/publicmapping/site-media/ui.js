$(function() {
		$('#steps').tabs();
    
    $('button').button();
    
   
    $('.menu_toggle')
        .button({
          icons: {primary: 'ui-icon-triangle-1-s'},text: false})
        .toggle(
          function(){
            $(this).button({icons: {primary: 'ui-icon-triangle-1-e'}})
          },
          function(){
            $(this).button({icons: {primary: 'ui-icon-triangle-1-s'}})
          })
        .click(function(){
          $('.map_menu_content').slideToggle(200);
        });
        
    $('#toolset_draw .toolset_group button').button({
        icons: {primary: 'ui-icon'},
        text:false
    });    

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
