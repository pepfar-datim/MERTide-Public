'use strict';

/**
 * STELLA: Sub Total ELement Lazy Adderupper
 *  Adds up column, row, and group numeric totals
 * @author: Greg Wilson <gwilson@baosystems.com>
 * @requires: dhis2 utils
 */

/**
 * Assumptions:
 * Subindicators are wrapped in a class prefixed with si_ followed by a unique 8 alnum (eg. si_aaaaaaaa)
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
 * stella.autocalcrules is an array of rules, where each rule has the target as index 0
 * and the array of sources and category option combos as index 1.
 * stella.autocalcindex is a hash, where the SSID is the key and an array of indices of rules 
 * from stella.autocalcrules is the value.
 */
stella.autocalc = function (target, source) {
  stella.autocalcrules.push([target, source]);
  source.forEach(function(s) {
    if (!(s[0] in stella.autocalcindex)) {
      stella.autocalcindex[s[0]] = [];
    }
    stella.autocalcindex[s[0]].push(stella.autocalcrules.length - 1);
    stella.updateSubindicatorTotal(source, target);
  });
};

/**
 * Subtotal calculation when a data value changes
 */
stella.changed = function (dv) {
  //get the element that was changed
  var si = "";
  //find the particular sub indicator group that was modified
  $('[class*="si_"]').each(function (i, d) {
    var c = $(this).attr('class');
    var this_si = c.substr(c.indexOf('si_') + 3, 8);
    if ($(this).find("[id^=" + dv.de + "]").length > 0) {
      si = this_si;
      return;
    }
  });

  if (si !== "") {
    stella.updateSubindicatorTotal([si], si);
    if (si in stella.autocalcindex) {
      stella.autocalcindex[si].forEach(function(e) {
        stella.updateSubindicatorTotal(stella.autocalcrules[e][1], stella.autocalcrules[e][0]);
      });
    }
  }
};

/**
 * Subtotal calculation for a particular subindicator
 */
stella.updateSubindicatorTotal = function (source, target) {
  var rows = []; //assigned to rows
  var cols = []; //assigned to columns
  var all = []; //all the non-empty values
  //regexes for getting which particular row/col we re looking at
  var re_row = /row([0-9]{1,2})/;
  var re_col = /col([0-9]{1,2})/;

  //enter these specific subindicators
  source.forEach(function (s) {
    var si, cocs;
    if (Array.isArray(s)) {
      si = s[0];
      cocs = s[1];
    } else {
      si = s;
      cocs = false;
    }
    $(".si_" + si).each(function (i, d) {
      //get all the entry divs
      $(this).find('[class*=Form_EntryField]').each(function (j, m) {
        var val = 0;
        var classes = $(this).attr('class');
        //skip the 'total' fields
        if (classes.indexOf('tot') >= 0) {
          return;
        }
        //get the input object
        var input = $(this).find("input");

        //if we're only selecting a specific category option combo, check to see whether this input has an id and
        //whether that coc is referenced in that id
        if (cocs) {
          var ignore = true;
          if (typeof($(input).attr('id')) === 'undefined') {
            return;
          }
          for (var c = 0; c < cocs.length; c++) {
            if ($(input).attr('id').indexOf(cocs[c]) !== -1) {
              ignore = false;
              continue;
            }
          }
          if (ignore) {
            return;
          }
          val = input.val();
        } else {
          val = input.val();
        }

        //we didn't end up with a value, so check to see if we are in reports instead
        if (val === undefined) {
          val = parseInt($(this).find(".val").text());
        }
        if (isNaN(val)) {
          //ignore
        } else {
            var v = Number(val);
            //stick it in the right bucket(s)
            if (source[0] == target) {
              var row = re_row.exec(classes);
              var col = re_col.exec(classes);
              if (row && row.length === 2) {
                if (!rows[row[1]]) {
                  rows[row[1]] = [];
                }
                if (val !== '') {
                  rows[row[1]].push(v);
                }
              }
              if (col && row.length === 2) {
                if (!cols[col[1]]) {
                  cols[col[1]] = [];
                }
                if (val !== '') {
                  cols[col[1]].push(v);
                }
              }
            }
            if (val !== '') {
              all.push(v);
            }
          }
      });
    });

    //update the page
    if (source[0] == target) {
      rows.forEach(function (d, i) {
        $('.totrow' + i + '_' + source).each(function () {
          stella.sum_and_display(this, d);
        });
      });
      cols.forEach(function (d, i) {
        $('.totcol' + i + '_' + source).each(function () {
          stella.sum_and_display(this, d);
        });
      });
    }
    $(".total_" + target).each(function () {
      stella.sum_and_display(this, all);
    });
  });
};

/**
 * On-load method to update all subindicator totals
 */
stella.load = function () {
  $('[class*="si_"]').each(function (i, d) {
    var c = $(this).attr('class');
    var si = c.substr(c.indexOf('si_') + 3, 8);
    stella.updateSubindicatorTotal([si], si);
  });
};

/**
 * Helper: reduce a data array to its sum and place it into the corresponding child input.
 */
stella.sum_and_display = function (element, data) {
  if (data.length > 0) {
    var sum = data.reduce(function (a, b) {
      return a + b;
    }, 0);
    //round to 2 sig figs
    if (sum.toFixed(2).indexOf(".00") == -1) {
      sum = sum.toFixed(2);
    }
    $(element).find('.input_total').text(sum);
  } else {
    $(element).find('.input_total').html('<span class="word_subtotal">Subtotal</span>');
  }
};