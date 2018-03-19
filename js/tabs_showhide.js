$(function () {
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