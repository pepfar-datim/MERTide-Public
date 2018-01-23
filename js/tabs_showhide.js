$(function () {
	$("#PEPFAR_Tabs_vertical").tabs().addClass("ui-tabs-vertical ui-helper-clearfix").removeClass("ui-tabs");;

	$("#PEPFAR_Tabs_vertical li").removeClass("ui-corner-top").addClass("ui-corner-left");
	$("[id ^= PEPFAR_Tabs_h]").tabs();

	$('.PEPFAR_Form_Title').click(function (e) {
		var SH = this.SH ^= 1; // "Simple toggler"
		$(this).toggleClass("expanded")
			   .next(".PEPFAR_Form_Collapse").slideToggle();
	});

	$('.PEPFAR_Form_ShowHide').click(function (e) {
		var SH = this.SH ^= 1; // "Simple toggler"
		//$(this).text(SH ? 'Expand All' : 'Collapse All')
		$(this).toggleClass("expanded");
		if (SH)
			$(this).parent().find(".PEPFAR_Form_Title").addClass('expanded')
				.next(".PEPFAR_Form_Collapse").slideUp();
		else
			$(this).parent().find(".PEPFAR_Form_Title", this.parent).removeClass('expanded')
				.next(".PEPFAR_Form_Collapse").slideDown();
	});
});