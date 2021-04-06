if (window.dhis2) {
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
}

var functionloader = {};
functionloader.dataSetToRunFor = false;
functionloader.lastSelectedForm = false;

functionloader.setToLoading = function(loadingStatus) {
  if (loadingStatus) {
    $('#contentDiv').hide();
    $('#loaderDiv').children('p').text('Please wait while the PEPFAR data entry form is loading...');
    $('#loaderDiv').show();
  } else {
    setTimeout(function() {
      $('#loaderDiv').hide();
      $('#PEPFAR_main').show();
      $('#contentDiv').show();
    }, 500);

  }    
}

functionloader.dataValuesLoaded = function (ds) {
  functionloader.setToLoading(true);
  if (!functionloader.dataSetToRunFor) {
    // dataSetToRunFor is not set, so this is the first time we've been run
    console.log('PEPFAR: MER | Custom JS Loaded: v20201130 | Loading all javascript for ' + ds);
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
    functionloader.setToLoading(false);

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
    functionloader.setToLoading(false);
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
    functionloader.setToLoading(false);
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

functionloader.showAndHideTabs = function() {
  $(function () {
    $('.PEPFAR_Form_Title').click(function (e) {
      $(this).toggleClass("expanded")
      .next(".PEPFAR_Form_Collapse").slideToggle();

      var divText = $(this).text(); 
      var ls = window.localStorage.getItem('userCollapsed') || '{}';
      ls = JSON.parse(ls);

      if ($(this).hasClass('expanded')) {
        // we are collapsing
        ls[divText] = true;
        var expandedCount = 0;
        // after this element is collapsed, we check if any items are still expanded
        // if all elements are collapsed, we need to change functionality to expand all`
        // we check that all elements are collapsed, by seeing if count of expanded items === 0
        $(this).parent().siblings().find('.PEPFAR_Form_Title').each(function(el) {
            if (!$(this).hasClass('expanded')) {
              expandedCount += 1;
              return false;
            }
        })
        if (expandedCount === 0) {
          $(this).parent().siblings('.PEPFAR_Form_ShowHide').addClass('expanded');
        }           
      } else {
        // we are expanding
        ls[divText] = false;
        // if expanding, we should make sure the default `Collapse All` is displayed
        $(this).parent().siblings('.PEPFAR_Form_ShowHide').removeClass('expanded');
      }  
      window.localStorage.setItem('userCollapsed', JSON.stringify(ls)); 
    });

    $('.PEPFAR_Form_ShowHide').click(function (e) {
        var ls = window.localStorage.getItem('userCollapsed') || '{}';
        ls = JSON.parse(ls);
        var currentlyExpandAll = $(this).hasClass('expanded'); //we are expanding if true

        $(this).siblings().find('.PEPFAR_Form_Title').each(function (el) {
        var divText = $(this).text();
        ls[divText] = !currentlyExpandAll //userCollapsed is true if expanding is false (and vice versa)
        if ($(this).hasClass('expanded') && currentlyExpandAll) {
          $(this).removeClass('expanded')
          .next(".PEPFAR_Form_Collapse").slideDown();
        }
        if (!$(this).hasClass('expanded') && !currentlyExpandAll) {
          $(this).addClass('expanded')
          .next(".PEPFAR_Form_Collapse").slideUp();
        }      
      })
      
      $(this).toggleClass("expanded");
        window.localStorage.setItem('userCollapsed', JSON.stringify(ls)); 
    });
  });
}

if (!window.dhis2 || !window.jQuery) {
  var dnj = document.createElement('script');
  dnj.type = 'text/javascript';
  dnj.async = false;
  dnj.src = '/api/apps/Data-Approval/formJs/jqueryAndDhis.js';
  dnj.onload = function () {
    $ = jQuery;
    functionloader.dataValuesLoaded('unknown dataset');
    functionloader.showAndHideTabs();
  };
  (document.getElementsByTagName('head')[0] || document.getElementsByTagName('body')[0]).appendChild(dnj);
} else {
  functionloader.showAndHideTabs();
}
