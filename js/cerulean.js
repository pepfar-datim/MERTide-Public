'use strict';

/**
 * CERULEAN: Make conditional areas expandable
 * @author: Greg Wilson <gwilson@baosystems.com>
 * @requires: jQuery
 */

var cerulean = {};

cerulean.toggle = function (div) {
  var element = $(div).parent().parent().parent();
  element.siblings().toggle();
  $(div).children().toggle();
};

/**
 * On-load check for what should be hidden
 */
cerulean.load = function () {
  //add the buttons
  var buttons = $('<div class="cerulean" style="float:right;color:red"><span><i class="fa fa-minus-square-o" aria-hidden="true"></i> Collapse</span><span><i class="fa fa-plus-square-o" aria-hidden="true"></i> Expand</span>').appendTo(".PEPFAR_Form_Priority_conditional > .PEPFAR_Form_Description").click(function () {
    cerulean.toggle(this);
  });
  //set up initial state
  buttons.each(function () {
    $(this).children().last().toggle();
    cerulean.toggle(this);
  });
};