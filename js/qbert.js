'use strict';

/**
 * qbert: Quarter Based Form Locking
 *  Hides subforms if not in currently selected time period
 * @author: Greg Wilson <gwilson@baosystems.com>
 * @requires: dhis2 utils
 */

/**
 * Assumptions:
 */

var qbert = {};

//get the currently selected dataset/period/org
qbert.getPeriod = function () {
  return $('#selectedPeriodId').val();
};

qbert.reset = function (form) {
  //Expand
  $(form).removeClass('expanded').next(".PEPFAR_Form_Collapse").slideDown();
  //reset the Title
  $(form).removeClass('ic_title_disabled');
  //make sure the title class is present
  //$(form).addClass('PEPFAR_Form_Title'); //Not sure why this was necessary (TH)
  //set input elements as RO
  $(form).parent().find("input").each(function () {
    qbert._enable(this);
  });
  $(form).parent().find("textarea").each(function () {
    qbert._enable(this);
  });
  //remove warning text
  //        append("div").removeClass("cadenceWarning").html("");
};

//find and disable form elements
qbert.disable = function (form) {
  //Collapse
  $(form).addClass('expanded').next(".PEPFAR_Form_Collapse").slideUp('fast');
  //grey out title
  $(form).addClass('ic_title_disabled');
  //remove existing Title Class (for collapse/expanding)
  //$(form).removeClass('PEPFAR_Form_Title'); //Not sure why this was necessary (TH)
  //set input elements as RO
  $(form).parent().find("input").each(function () {
    qbert._disable(this);
  });
  //set input elements as RO
  $(form).parent().find("textarea").each(function () {
    qbert._disable(this);
  });
  //add warning text
  //        append("div").addClass("cadenceWarning").html("Invalid time period. Data entry disabled.");
};

//disable a form element
qbert._disable = function (elem) {
  if ($(elem).val() === '') {
    $(elem).addClass('ic_disabled').prop('disabled', true);
  } else {
    $(elem).addClass('ic_disabled').prop('disabled', false);
  }
};

qbert._enable = function (elem) {
  $(elem).removeClass('ic_disabled').prop('disabled', false).removeClass("ic_conflict");
};

/**
 * On-load method to update which sections are visible
 */
qbert.load = function () {
  var period = qbert.getPeriod();
  //parse the current period
  var re = /20[1-9][0-9]Q([1-4])/; //we don't expect this to be running in 2100
  var found = period.match(re);

  if (found !== null) {
    //Reset the indicators
    var noentry = $(".ic_title_disabled");
    $(noentry).each(function () {
      qbert.reset(this);
    });

    //only show annual in Q4 of FYOCT
    if (found[1] === '4' || found[1] === '1' || found[1] === '2') {
      var anns = $(".PEPFAR_Form_Title_Annually");
      $(anns).each(function () {
        qbert.disable(this);
      });
    }
    //only show semi in Q2, Q4 of FYOCT
    if (found[1] === '4' || found[1] === '2') {
      var qs = $(".PEPFAR_Form_Title_Semiannually");
      $(qs).each(function () {
        qbert.disable(this);
      });
    }
    //always show quarterly (PEPFAR_Form_Title_Quarterly)
  }
};