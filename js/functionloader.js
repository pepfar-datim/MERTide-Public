(function() {
  dhis2.util.on(dhis2.de.event.dataValuesLoaded, function(event, ds) {
    functionloader.dataValuesLoaded(ds);
  });

  dhis2.util.on(dhis2.de.event.formReady, function(event, ds) {
    //Form ready extra js to run
    //#formReady#
  });
})();

dhis2.util.on(dhis2.de.event.dataValueSaved, function(event, ds, dv) {
  stella.changed(dv);
  meany.changed(dv);

  //dataValueSaved extra JS to run
  //#dataValueSaved#
});

var functionloader = {};
functionloader.dataSetToRunFor = false;
functionloader.lastSelectedForm = false;

functionloader.dataValuesLoaded = function (ds) {
  $('#PEPFAR_loading').show();
  if (!functionloader.dataSetToRunFor) {
    // dataSetToRunFor is not set, so this is the first time we've been run
    console.log('PEPFAR: MER | Custom JS Loaded: v20190114 | Loading all javascript for ' + ds);
    functionloader.erase();
    functionloader.dataSetToRunFor = ds;
    functionloader.lastSelectedForm = functionloader.identifySelectedForm();
    qbert.load();

    $('.PEPFAR_Form_EntryField').find('.entryfield').addClass('PEPFAR_Form_EntryField_input');
    $('.PEPFAR_Form_OptionSet').find('.entryoptionset').addClass('PEPFAR_Form_EntryField_optionset');
    $('.PEPFAR_Form_Narrative').find('.entryarea').addClass('PEPFAR_Form_EntryField_narrative');

    //Data Values Loaded extra js to run
    //#dataValuesLoaded#

    functionloader.loadWithDelay();

  } else if (functionloader.dataSetToRunFor == ds && functionloader.lastSelectedForm && functionloader.lastSelectedForm == functionloader.identifySelectedForm()) {
    // dataSetToRunFor is set, but this appears to be the same form, due to a quirk in DHIS 2 
    // that causes dataValuesLoaded to be called twice, so we do nothing
    console.log('PEPFAR: MER | dataValuesLoaded with previous ' + ds + ' and the same form, doing nothing');
    functionloader.lastSelectedForm = functionloader.identifySelectedForm();
    $('#PEPFAR_loading').hide();

  } else if (functionloader.dataSetToRunFor == ds) {
    // dataSetToRunFor is set, and either we are not able to determine the last selected form or it's a different form
    // Therefore, don't reconstruct the rules, but reload them on the page
    console.log('PEPFAR: MER | dataValuesLoaded with previous ' + ds + ', reloading custom JS');
    functionloader.erase();
    functionloader.lastSelectedForm = functionloader.identifySelectedForm();
    qbert.load();
    functionloader.loadWithDelay();

  } else {
    // Due to another quirk in DHIS 2, this javascript might be trying to run for a different form, as DHIS 2
    // may not wipe out custom javascript if the new form is not a custom form or does not have custom javascript.
    // Therefore, we delete our variables and reset all of the CSS, JS, and the like
    console.log('PEPFAR: MER | ' + functionloader.dataSetToRunFor + ' does not match ' + ds + ', so custom JS should not run; clearing out saved variables');
    functionloader.lastSelectedForm == false;
    functionloader.erase();
    meany.kill();
    stella.kill();
    $('#PEPFAR_loading').hide();
  }
}

functionloader.erase = function () {
  qbert.erase();
  meany.erase();
  stella.erase();
  cerulean.erase();
}

/**
 * After a short delay to allow execution of form display code, load cerulean, stella, and meany
 * Then remove the gray background formatting that DHIS2 applied to form fields that were disabled, but no longer are
 */
functionloader.loadWithDelay = function () {
  setTimeout(function() {
    cerulean.load();
    stella.load();
    meany.load();
    $('.entryfield').each(function(index) {
      if ($(this).css('background-color') != 'rgb(255, 255, 255)' && !$(this).hasClass('disabled')) {
        $(this).css('background-color', 'rgb(255, 255, 255)');
      }
    });
    $('#PEPFAR_loading').hide();
  }, 10);
}

/**
 * Uniquely identify the form, by adding the uid from the org hierarchy to the various selections from the selection box
 * and turn them all into a string
 */
functionloader.identifySelectedForm = function () {
  var orgUnit = $('#orgUnitTree .selected').parent('li').attr('id');
  if (typeof(orgUnit) !== 'undefined') {
    return $('#orgUnitTree .selected').parent('li').attr('id') + ' ' +
      Object.values($('#selectedDataSetId,#selectedPeriodId,#category-SH885jaRe0o')
        .map(function() { 
          return $(this).val(); 
        }).sort()
      ).join(' ');
  } else {
    return false;
  }
}
