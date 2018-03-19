'use strict';

/**
 * MEANY: Mutually Exclusivity Automatic Nickel Yak
 *  Disables input fields based on user-entered data from rules 
 *  created by mertide.py and established at form load
 * @author: Greg Wilson <gwilson@baosystems.com> and Ben Guaraldi <ben@dhis2.org>
 * @requires: dhis2 utils
 */

var meany = {};

meany.autoexcludeindex = {};
meany.autoexcluderules = [];

/**
 * Load autoexclude rules into meany.autoexcluderules and meany.autoexcludeindex.
 *
 * meany.autoexcluderules is an array of rules, where one side of the mutually exclusive rule (muex)
 * is index 0 and the other side is index 1. Both indices could either be just a specific subindicator id
 * (ssid) or an array of ssids and category option combos (coc).
 *
 * meany.autoexcludeindex is a hash, where the ssid is the key and the value is an array of indices
 * of rules from meany.autoexcluderules.  If the rule index is negative, it refers to a flipped version 
 * of the rule represented by the equivalent positive number.
 */
meany.autoexclude = function (left, right) {
  // Add the rule to autoexcluderules
  meany.autoexcluderules.push([left, right]);

  // Consider each operand of the left side
  left.forEach(function(l) {
    // l[0] is the ssid, which is the key for autoexcludeindex
    // (l[1], if it exists, is an array of cocs to consider;
    // any other cocs are ignored)

    // If we haven't seen this ssid, make an empty array for it
    if (!(l[0] in meany.autoexcludeindex)) {
      meany.autoexcludeindex[l[0]] = [];
    }

    // Add this rule to autoexcludeindex
    meany.autoexcludeindex[l[0]].push(meany.autoexcluderules.length);
  });

  // Consider each operand of the right side, just like the left side
  right.forEach(function(r) {
    if (!(r[0] in meany.autoexcludeindex)) {
      meany.autoexcludeindex[r[0]] = [];
    }
    // Create a negative rule index so we know the rule should be flipped
    // before evaluating it from the right side's perspective
    meany.autoexcludeindex[r[0]].push(-1 * meany.autoexcluderules.length);
  });

  // Evaluate the rule from both perspectives, to see if anything on the form
  // needs to be disabled or enabled
  meany.evaluateRuleConsequences([left, right], false);
  meany.evaluateRuleConsequences([right, left], false);
}

/**
 * When a form value is changed, consider each relevant mutual exclusion rule to determine 
 * whether any form fields need to be hidden or shown
 */
meany.changed = function (dv) {
  // Find the particular sub indicator group that was modified using the de and co properties 
  // of dv from DHIS 2's dataValueSaved function
  var ssid = '';
  $('[class*="si_"]').each(function (i, d) {
    if ($(this).find('[id^=' + dv.de + '-' + dv.co + ']').length > 0) {
      var c = $(this).attr('class');
      ssid = c.substr(c.indexOf('si_') + 3, 8);
      return;
    }
  });

  if (ssid !== '') {
    if($('input[id^=' + dv.de + '-' + dv.co + '-val]').hasClass('muex_conflict')) {
      // The recently edited field has a conflict, so perhaps it needs to be disabled
      meany.disableOperand([ssid, [dv.co]]);
      meany.maybeEnableOperand([ssid, [dv.co]]);
    }
    if (ssid in meany.autoexcludeindex) {
      // If we have rules in the autoexcludeindex for this ssid, operate them
      meany.autoexcludeindex[ssid].forEach(function(index) {
        meany.evaluateRuleConsequences(meany.getRule(index), dv.co);
      });
    }
  }
};

/**
 * Given an index, return the rule that corresponds to that index.
 */
meany.getRule = function (index) {
  if (index > 0) {
    // This rule has a positive index, so it is not flipped
    return meany.autoexcluderules[index - 1];

  } else {
    // If the rule's index is negative, then it's actually saying swap the sides of the 
    // positive index rule.  So if the rule is "values in A mean that there should be 
    // no values in B" and flip it to "values in B mean there should be no values in A"

    // So first, find the rule to flip, which is -1 times the index minus 1
    var original = meany.autoexcluderules[(-1 * index) - 1];

    // Now, flip the rule and return it
    return [original[1], original[0]];
  }
}

/**
 * Consider a specific mutual exclusion rule and decide whether any form fields need to be hidden or shown.
 *
 * This function only considers one direction of the mutual exclusion, so it's looking at the fields on the left side
 * to determine whether the fields on the right side should be hidden or shown.
 */
meany.evaluateRuleConsequences = function (rule, coc) {
  var hasValues = false;

  // Consider each operand on the left side
  for (var o = 0; o < rule[0].length; o++) {
    var lcocs = rule[0][o][1];
    // If we're targeting a rule to specific category option combos and this data value
    // isn't associated with that category option combo, we can ignore it
    if (coc && lcocs && !lcocs.includes(coc)) {
      continue;
    }
    hasValues = meany.checkValues(rule[0][o]);
    // If any of the left side has values, we can stop looking for values
    if (hasValues) {
      break;
    }
  }

  for (var o = 0; o < rule[1].length; o++) {
    // We disable the right side if there were any values in the left side;
    // otherwise, we maybe enable it
    if (hasValues) {
      meany.disableOperand(rule[1][o]);
    } else {
      meany.maybeEnableOperand(rule[1][o]);
    }
  }
}

/**
 * Consider an operand (split into an ssid and an array of cocs) and determine whether it has any values.
 */
meany.checkValues = function (operand) {
  var ssid, cocs;
  [ssid, cocs] = operand;

  // Examine all instances of this ssid (which is probably just one)
  for (var i = 0; i < $('.si_' + ssid).length; i++) {
    // Get all the entry divs
    var entryDivs = $('.si_' + ssid + ':eq(' + i + ')').find('[class*=Form_EntryField]');
    for (var j = 0; j < entryDivs.length; j++) {
      var entryDiv = entryDivs[j];
      var input = $(entryDiv).find('input');

      // Skip the total fields.  Also, if we're only selecting a specific category option combo, 
      // check to see whether this input has an id and whether that coc is referenced in that id
      if ($(entryDiv).attr('class').indexOf('tot') === -1 && (!cocs || meany.idHasCoc($(input).attr('id'), cocs))) {
        var val = $(input).val();
        if (typeof(val) === 'undefined') {
          val = $(entryDiv).find('.val').text();
          if (typeof(val) !== 'undefined' && val != '') {
            return true;
          }
        } else if (val != '') {
          return true;
        }
      }
    }
  }
  return false;
};

/**
 * Determine whether a given id references a coc
 */
meany.idHasCoc = function (id, cocs) {
  if (typeof id === 'undefined') {
    return false;
  }
  for (var c = 0; c < cocs.length; c++) {
    if (id.indexOf(cocs[c]) !== -1) {
      return true;
    }
  }
  return false;
}

/**
 * Check to see whether one side of a rule has an operand that matches
 * a particular ssid and coc
 */
meany.operandMatch = function (side, ssid, coc) {
  for (var o = 0; o < side.length; o++) {
    if (side[o][0] === ssid && (typeof side[o][1] === 'undefined' || side[o][1].includes(coc))) {
      return true;
    }
  }
  return false;
}

/**
 * Check to see whether a rule indicates that a certain field (defined by ssid and coc)
 * should remain disabled
 */
meany.keepCocDisabled = function (rule, ssid, coc) {
  if (coc === 'all' || meany.operandMatch(rule[0], ssid, coc)) {
    for (var o = 0; o < rule[1].length; o++) {
      if (meany.checkValues(rule[1][o])) {
        return true;
      }
    }
  }
  return false;
};

/**
 * Consider an operand that has had one mutual exclusion removed to see if it has other mutual exclusions
 * restricting it, or if it should be enabled.  Since any rule can target any coc, this must be done on a 
 * field-by-field basis.
 */
meany.maybeEnableOperand = function (operand) {
  var ssid, cocs;
  [ssid, cocs] = operand;
  if (ssid !== '' && ssid in meany.autoexcludeindex) {
    var keepCocDisabled = {};
    if (!cocs) {
      cocs = ['all'];
    }
    for (var c = 0; c < cocs.length; c++) {
      keepCocDisabled[cocs[c]] = false;

      // Since mutually exclusive rules are symmetric, we can check to see if any fields
      // require this field to remain disabled, and if not, enable it
      for (var i = 0; i < meany.autoexcludeindex[ssid].length; i++) {
        var index = meany.autoexcludeindex[ssid][i];
        var rule = meany.getRule(index);
        keepCocDisabled[cocs[c]] = meany.keepCocDisabled(rule, ssid, cocs[c]);
        if (keepCocDisabled[cocs[c]]) {
          break;
        }
      }
    }
    
    for (c = 0; c < cocs.length; c++) {
      if (!keepCocDisabled[cocs[c]]) {
        if (cocs[c] == 'all') {
          $('.si_' + ssid).find('input:not([readonly])').prop('disabled', false).removeClass('muex_disabled').removeClass('muex_conflict');
        } else {
          $('.si_' + ssid).find('input[id*=' + cocs[c] + ']:not([readonly])').prop('disabled', false).removeClass('muex_disabled').removeClass('muex_conflict');
        }
      }
    }
  }
};

/**
 * Disable a particular mutually exclusive operand
 */
meany.disableOperand = function (operand) {
  var ssid, cocs;
  [ssid, cocs] = operand;
  if (cocs) {
    cocs.forEach(function(c) {
      $('.si_' + ssid).find('input[id*=' + c + ']:not([readonly])').filter(function() { return this.value != ''; }).prop('disabled', false).addClass('muex_conflict').removeClass('muex_disabled');
      $('.si_' + ssid).find('input[id*=' + c + ']:not([readonly])').filter(function() { return this.value == ''; }).prop('disabled', true).addClass('muex_disabled').removeClass('muex_conflict');
    });
  } else {
    // Just disable the whole thing
    $('.si_' + ssid).find('input:not([readonly])').filter(function() { return this.value != ''; }).prop('disabled', false).addClass('muex_conflict').removeClass('muex_disabled');
    $('.si_' + ssid).find('input:not([readonly])').filter(function() { return this.value == ''; }).prop('disabled', true).addClass('muex_disabled').removeClass('muex_conflict');
  }
};

/**
 * Reset all form fields to enabled, before loading the rules that may disable them
 */
meany.reset = function () {
  $('input.muex_conflict').each(function () {
    $(this).prop('disabled', false).removeClass('muex_conflict');
  });

  $('input.muex_disabled').each(function () {
    $(this).prop('disabled', false).removeClass('muex_disabled');
  });
};