'use strict';

/**
 * MEANY: Mutually Exclusivity Automatic Nickel Yak
 *  Searches for mew_* classes and disables the corresponding input fields
 * @author: Greg Wilson <gwilson@baosystems.com>
 * @requires: dhis2 utils
 */

/**
 * Input groups that require mutual exclusivity should have two classes:
 *   si_AAAAAAAA mew_BBBBBBBB
 * where "si" stands for "sub-indicator". AAAAAAAA and BBBBBBBB are 8 random
 * alnum codes. In this case, the fields in this sub indicator would be exclusive
 * to fields in the "si_BBBBBBBB mew_AAAAAAAA" section.
 */

var meany = {};

meany.changed = function (dv) {
  //full check for conflicts first
  meany.check();

  //get the element that was changed
  var muex = "";

  //see if we need to re-enable anything
  $('[class*="mew_"]').each(function (i, d) {
    //get this muex ID
    var c = $(this).attr('class');
    var thismuex = c.substr(c.indexOf('mew_') + 4, 8);
    if ($(this).find("[id^=" + dv.de + "]").length > 0) {
      muex = thismuex;
      return;
    }
  });
  if (muex !== '' && dv.value === '') {
    meany.enable(muex);
  }
};

/**
 * Disable a particular MUEX section
 */
meany.disable = function (muex) {
  $(".si_" + muex).find("input:not([readonly])").prop('disabled', true).addClass("muex_disabled");
};

/**
 * Re-enable a section if it's corresponding muex was cleared
 */
meany.enable = function (muex) {
  var clear = true;
  //if all data is cleared out, re-enable the corresponding muex
  $(".mew_" + muex).find("input:not([readonly])").each(function () {
    if ($(this)[0].value !== "") {
      //if there is at least 1 value still set, no need to examine the rest
      clear = false;
      return;
    }
  });
  //do we need to re-enable the other section?
  if (clear === true) {
    //all entries are cleared out in the modified section. re-enable the other section if disabled
    $(".si_" + muex).find("input:not([readonly])").prop('disabled', false).removeClass("muex_disabled");
    //nothing else should be disabled
    return;
  }
};

meany.reset = function () {
  $("input.muex_conflict").each(function () {
    $(this).prop('disabled', false).removeClass('muex_conflict');
  });

  $("input.muex_disabled").each(function () {
    $(this).prop('disabled', false).removeClass('muex_disabled');
  });
};

/**
 * Perform MUEX conflict check and locking
 */
meany.check = function () {

  //reset muex_* before checking. Hopefully not too much flicker...
  meany.reset();

  $('[class*="mew_"]').each(function (i, d) {
    //mews will have corresponding si_
    var c = $(this).attr('class');
    var thismuex = c.substr(c.indexOf('mew_') + 4, 8);
    var this_si = c.substr(c.indexOf('si_') + 3, 8);

    var stor_mew = [];
    var stor_si = [];
    //does muex have values?
    $(".mew_" + thismuex).find("input:not([readonly])").each(function () {
      if ($(this).val() !== '') {
        stor_mew.push(this);
      }
    });
    //does corresponding si have values?
    $(".si_" + thismuex).find("input:not([readonly])").each(function (k, v) {
      if ($(this).val() !== '') {
        stor_si.push(this);
      }
    });
    //the converse will be done on the next pass. Not efficient, but whatever.

    if (stor_mew.length > 0 && stor_si.length == 0) {
      meany.disable(thismuex);
      return;
    }
    if (stor_mew.length == 0 && stor_si.length > 0) {
      meany.disable(this_si);
      return;
    }
    if (stor_mew.length > 0 && stor_si.length > 0) {
      //due to lag or something else, a conflict made it through.
      //lock that section of the form
      meany.disable(thismuex);
      meany.disable(this_si);
      //flag the conflict but don't disable since it needs to be fixed
      var _iteratorNormalCompletion = true;
      var _didIteratorError = false;
      var _iteratorError = undefined;

      try {
        for (var _iterator = stor_mew[Symbol.iterator](), _step; !(_iteratorNormalCompletion = (_step = _iterator.next()).done); _iteratorNormalCompletion = true) {
          var field = _step.value;

          $(field).addClass('muex_conflict').prop('disabled', false).removeClass("muex_disabled");
        }
      } catch (err) {
        _didIteratorError = true;
        _iteratorError = err;
      } finally {
        try {
          if (!_iteratorNormalCompletion && _iterator.return) {
            _iterator.return();
          }
        } finally {
          if (_didIteratorError) {
            throw _iteratorError;
          }
        }
      }

      ;
      var _iteratorNormalCompletion2 = true;
      var _didIteratorError2 = false;
      var _iteratorError2 = undefined;

      try {
        for (var _iterator2 = stor_si[Symbol.iterator](), _step2; !(_iteratorNormalCompletion2 = (_step2 = _iterator2.next()).done); _iteratorNormalCompletion2 = true) {
          var _field = _step2.value;

          $(_field).addClass('muex_conflict').prop('disabled', false).removeClass("muex_disabled");
        }
      } catch (err) {
        _didIteratorError2 = true;
        _iteratorError2 = err;
      } finally {
        try {
          if (!_iteratorNormalCompletion2 && _iterator2.return) {
            _iterator2.return();
          }
        } finally {
          if (_didIteratorError2) {
            throw _iteratorError2;
          }
        }
      }

      ;
      return;
    }
  });
};

/**
 * On-load check for what should be disabled
 */
meany.load = function () {
  meany.check();
};