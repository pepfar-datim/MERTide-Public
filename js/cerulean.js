'use strict';

/**
 * CERULEAN: Make sections of forms designated "conditional" expandable and contractible
 * @author: Greg Wilson <gwilson@baosystems.com> and Ben Guaraldi <ben@dhis2.org>
 * @requires: jQuery
 */

var cerulean = {};

/**
 * On load of form, add expand/collapse buttons and hide sections that do not have values
 */
cerulean.load = function () {
  // Remove old buttons
  $('.cerulean').remove();
  // Add new buttons
  var buttonDiv = '<div class="cerulean"><span><i class="fa fa-minus-square-o" aria-hidden="true"></i> Collapse</span><span><i class="fa fa-plus-square-o" aria-hidden="true"></i> Expand</span></div>';
  var buttons = $(buttonDiv).appendTo('.PEPFAR_Form_Priority_conditional > .PEPFAR_Form_Description').click(function () {
    cerulean.toggle(this);
  });
  // Set up initial state for each section, by considering each of the sets of buttons that was just created
  buttons.each(function () {
    // If there are no values, hide the conditional form section; otherwise, show it
    cerulean.toggle(this, cerulean.hasValues(this));
  });
};

/**
 * If visible is true, show the conditional area
 * If visible is false, hide the conditional area
 * If visible is undefined, then reverse the visibility of the conditional area
 * Also, make other necessary changes, like switching the text from Expand to Collapse or vice versa
 */
cerulean.toggle = function (buttonDiv, visible) {
  var sectionTitleDiv = $(buttonDiv).parent().parent().parent();
  if (visible === undefined) {
    // Turn on or off the conditional form area
    $(sectionTitleDiv).siblings().toggle();
    // Reverse the visibility of the Expand and Collapse divs, so only one shows at a time
    $(buttonDiv).children().toggle();
  } else {
    // If visible is true, show the conditional form area; otherwise, hide it
    $(sectionTitleDiv).siblings().toggle(visible);
    // If visible is true, show the Collapse button; otherwise, hide it
    $(buttonDiv).children().first().toggle(visible);
    // If visible is true, hide the Expand button; otherwise, show it
    $(buttonDiv).children().last().toggle(!visible);
  }
};

/**
 * Test to see if a selector has values
 */
cerulean.hasValues = function(selector) {
  // Get the entry fields
  var fields = $(selector).parent().parent().parent().parent().find('[class*=Form_EntryField]');

  // Consider them one at a time
  for (var i = 0; i < fields.length; i++) {
    var field = fields[i];
    var input = $(field).find('input');
    // Skip the total fields
    if ($(field).attr('class').indexOf('tot') === -1) {
      // Attempt to find the value using two different methods, as the html and css for
      // the Data Entry app and the Data Approval app are different
      var val = $(input).val();
      if (typeof(val) === 'undefined') {
        val = $(field).find('.val').text();
        if (typeof(val) !== 'undefined' && val != '') {
          return true;
        }
      } else if (val != '') {
        return true;
      }
    }
  }
  // We looked at all of the inputs in all of the fields and we didn't find any values
  return false;
};
