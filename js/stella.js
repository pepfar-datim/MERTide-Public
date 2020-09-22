'use strict';

/**
 * STELLA: Sub Total ELement Lazy Adderupper
 *  Adds up column, row, and group numeric totals
 * @author: Greg Wilson <gwilson@baosystems.com> and Ben Guaraldi <ben@dhis2.org>
 * @requires: dhis2 utils
 */

/**
 * Assumptions:
 * Specific subindicator ids (ssid) are wrapped in a class prefixed with 'si_' (for subindicator) 
 *   followed by a unique 8 alnum (eg. si_aaaaaaaa)
 * Each 'Form_EntryField' that contributed to a row or column count needs to have a
 *   respective "rowX" and "colY" class to indicate which row/column it contributes to.
 * Row total fields are readonly and have the class totrowX_aaaaaaaa where X is
 *   the row number and aaaaaaa is the same 8 alnum as the si_ class
 * Column total fields are readonly and have the class totcolY_aaaaaaaa where Y is
 *   the column number and aaaaaaa is the same 8 alnum as the si_ class
 * Grand "subtotal" fields are readonly and have the class total_aaaaaaaa where
 *   aaaaaaa is the same 8 alnum as the si_ class
 */

var stella = {};

stella.autocalcindex = {};
stella.autocalcrules = [];

/**
 * Load autocalc rules into stella.autocalcrules and stella.autocalcindex.
 *
 * stella.autocalcrules is an array of rules, where each rule has an array of operands to sum as index 0
 * and a single target to put that sum as index 1.   Each source could either be one specific subindicator id 
 * (ssid) or an array with index 0 as an ssid and index 1 with a set of category option combos (coc).
 *
 * stella.autocalcindex is a hash, where the ssid is the key and the value is an array of indices
 * of rules from stella.autocalcrules.
 */
stella.autocalc = function (source, target) {
  // Add the rule to autocalcrules
  stella.autocalcrules.push([source, target]);

  // Consider each operand of the source
  source.forEach(function(s) {
    // s[0] is the ssid, which is the key for autocalcindex
    // (s[1], if it exists, is an array of cocs to consider;
    // any other cocs are ignored)

    // If we haven't seen this ssid, make an empty array for it
    if (!(s[0] in stella.autocalcindex)) {
      stella.autocalcindex[s[0]] = [];
    }

    // Add this rule to autocalcindex if it's not already there
    if (stella.autocalcindex[s[0]].indexOf(stella.autocalcrules.length - 1) === -1) {
      stella.autocalcindex[s[0]].push(stella.autocalcrules.length - 1);
    }
  });
};

/**
 * Delete all loaded autocalculations
 */
stella.kill = function () {
  stella.autocalcindex = {};
  stella.autocalcrules = [];
};

/**
 * Remove all displayed autocalculations
 */
stella.erase = function () {
  $('[class*="si_"]').find('.input_total').html('<span class="word_subtotal">Subtotal</span>');
};

/**
 * Update rows, columns, non-custom and custom totals when loading the page
 */
stella.load = function () {
// Fix this so it just considers each row and each col and each total
  $('[class*="si_"]').each(function (i, d) {
    var ssid = this.className.match('si_(.{8})')[1]; // Use the ssid to sum
    stella.sumSlice(ssid, 'row');                    // the rows,
    stella.sumSlice(ssid, 'col');                    // the columns,
    stella.sumTotal([[ssid]], ssid);                 // and the non-custom totals
  });

  // For the custom totals, simply consider every rule once
  for (var r = 0; r < stella.autocalcrules.length; r++) {
    stella.sumTotal(stella.autocalcrules[r][0], stella.autocalcrules[r][1]);
  }
};

/**
 * When a form value is changed, consider autocalculation of rows, columns, totals, and custom rules 
 * to determine whether any form fields need to be changed
 */
stella.changed = function (dv) {
  // Find the particular sub indicator group that was modified using the de and co properties 
  // of dv from DHIS 2's dataValueSaved function
  var ssid = '';
  $('[class*="si_"]').each(function (i, d) {
    if ($(this).find('[id^=' + dv.de + '-' + dv.co + ']').length > 0) {
      ssid = this.className.match('si_(.{8})')[1];
      return;
    }
  });

  if (ssid !== '') {                    // If we have an ssid, then look at the related
    stella.sumSlice(ssid, 'row');       // rows,
    stella.sumSlice(ssid, 'col');       // columns,
    stella.sumTotal([[ssid]], ssid);    // totals,
    if (ssid in stella.autocalcindex) { // and custom rules
      stella.autocalcindex[ssid].forEach(function(e) {
        stella.sumTotal(stella.autocalcrules[e][0], stella.autocalcrules[e][1]);
      });
    }
  }
};

/**
 * Calculate the sums of a certain kind of slice of an ssid, usually either a row or a column
 */
stella.sumSlice = function (ssid, slice) {
  // An array to save the various sums of slices
  var slices = [];

  // Consider all Document Object Model (DOM) elements that match ssid
  $('.si_' + ssid).each(function () {
    // Get all of this DOM element's entry divs that have slice and that don't have 'tot'
    $(this).find('[class*=Form_EntryField][class*=' + slice + ']').not('[class*=tot]').each(function () {
      // Look for divs with 'slice' and then one or two numbers
      var s = this.className.match(slice + '\\d')[0];
      var val = stella.getVal(this);
      if (!slices[s]) {
        slices[s] = 0;
      }
      if (!isNaN(val)) {
        slices[s] += +val;
      }
    });
  });

  // Take all slices that we found display the sum we calculated
  for (var s in slices) {
    stella.display('.tot' + s + '_' + ssid, slices[s]);
  }
};

/**
 * Calculate the total sum for source, which is an array of operands, each with either just an ssid or an ssid
 * and cocs that restrict it.  Then place that total sum in target.  If created in an HTML template file, the
 * source and target will be the same ssid.  If specified in the CSV control file, they may be the same, but are
 * more likely to be different.
 */
stella.sumTotal = function (source, target) {
  var total = 0;

  // Consider each operand in source
  source.forEach(function (s) {
    var ssid = s[0];
    var cocs = s[1];

    // Consider all DOM elements that match ssid
    $('.si_' + ssid).each(function () {
      // Get all of this DOM element's entry divs, except for 'tot' fields
      $(this).find('[class*=Form_EntryField]').not('[class*=tot]').each(function () {
        // If we're only selecting a specific category option combo, check to see whether 
        // this input has an id and whether that coc is referenced in that id
        if (!cocs || stella.idHasCoc(this, cocs)) {
          // If we get a value, add it to the total
          var val = stella.getVal(this);
          if (!isNaN(val)) {
            total += +val;
          }
        }
      });
    });

    // Display the total sum in all DOM elements that match '.total_' + target.  (target is an ssid.)
    stella.display('.total_' + target, total);
  });
};

/**
 * Format a value and display it in all DOM elements matching selector.
 * If value is 0, show the text Subtotal in a small font.
 */
stella.display = function (selector, value) {
  $(selector).each(function () {
    if (value > 0) {
      // Round to 2 sig figs
      if (value.toFixed(2).indexOf('.00') == -1) {
        value = value.toFixed(2);
      }
      $(selector).find('.input_total').text(value);
    } else {
      $(selector).find('.input_total').html('<span class="word_subtotal">Subtotal</span>');
    }
  });
};

/**
 * Get the DHIS 2 data value related to a DOM selector
 */
stella.getVal = function(selector) {
  // Try to get the value through the input child of selector
  var val = $(selector).find('input').val();

  // We didn't end up with a value, so check to see if we are in reports instead
  if (val === undefined) {
    val = parseInt($(selector).find('.val').text());
  }

  return val;
};

/**
 * Determine whether a given id references a coc
 */
stella.idHasCoc = function (w, cocs) {
  try {
    var x = $(w).find('input');
    if (x.length) {
      var id = x.attr('id');  
    } else {
      x = $(w).find('span.val');
      if (!x.length) {
        return false;
      }
      var id = x.attr('data-de') + '-' + x.attr('data-co') + '-val';
    }

    for (var c = 0; c < cocs.length; c++) {
      if (id.indexOf(cocs[c]) !== -1) {
        return true;
      }
    }

    return false;

  } catch(e) {
    return false;
  }
};