$(function() {
  var _chart = null, _rssi = null, _ds = null, _mac = null, _firstseen, _lastseen;
  var tableau = ['#1f77b4', '#ff7f0e', '#2ca02c', /*'#d62728',*/ '#9467bd',
    '#8c564b', '#e377c2', /*'#7f7f7f',*/ '#bcbd22', '#17becf'];

  function median(values){
    if (values.length === 0) return 0;
    values.sort(function(a,b){
      return a-b;
    });
    var half = Math.floor(values.length / 2);
    if (values.length % 2) {
      return values[half];
    } else {
      return (values[half - 1] + values[half]) / 2.0;
    }
  }
  function* colorGenerator() {
    var c = 0;
    while (true) {
      yield tableau[c%tableau.length];
      c += 1;
    }
  }

  // https://stackoverflow.com/a/41491220/283067
  function pickTextColorBasedOnBgColorSimple(bgColor, lightColor, darkColor) {
    var color = (bgColor.charAt(0) === '#') ? bgColor.substring(1, 7) : bgColor;
    var r = parseInt(color.substring(0, 2), 16); // hexToR
    var g = parseInt(color.substring(2, 4), 16); // hexToG
    var b = parseInt(color.substring(4, 6), 16); // hexToB
    return (((r * 0.299) + (g * 0.587) + (b * 0.114)) > 186) ? darkColor : lightColor;
  }
  function updateDBTime() {
    $.ajax({
      url: '/api/stats/timestamp',
      dataType: 'json',
    }).done(function(data) {
      $('#dbtime').text(data.timestamp).css('text-decoration', '');
    }).fail(function(jq, status, error){
      $('#dbtime').css('text-decoration', 'line-through');
    });
  }

  function repack(data) {
    var ds = [], n = 0;
    var diameter = ($('#myChart').height()-50)/data.length-6;

    // repurpose our data in a format suitable for chart.js chart
    var gen = colorGenerator(), color;
    for (let d of data) {
      if (d.known) {
        color = '#d62728';
      } else if (d.mac == 'LAA') {
        color = '#7f7f7f';
      } else {
        color = gen.next().value;
      }
      var s = {
        label: d.mac,
        vendor: d.vendor,
        ssids: d.ssids,
        data: [],
        fill: false,
        pointStyle: 'line',
        pointRadius: diameter/2,
        pointRotation: 90,
        pointBorderColor: color,
        pointHoverRadius: diameter/2,
        pointHoverBorderColor: color,
        pointHoverBackgroundColor: color,
        backgroundColor: color, // for automatic legend only
        showLine: true,
        borderWidth: 1,
        borderColor: color+'44', // same as plot but with less alpha
      };
      for (let p of d.probereq) {
        s.data.push({'x': p.ts, 'y': data.length-1-n, 'rssi': p.rssi, 'ssid': p.ssid});
      }
      ds.push(s);
      n += 1;
    }
    return ds;
  }

  function drawRSSIChart(dataset, color) {
    var ctx = document.getElementById('RSSI').getContext('2d');
    var ds = [];
    for (let p of dataset) {
        ds.push({t: p.x, y:p.rssi});
    }
    var radius = 2;
    if (ds.length > 50) {
      radius = 1;
    }
    var points = {
      label: dataset.label,
      data: ds,
      fill: false,
      showLine: false,
      pointRadius: radius,
      pointBorderColor: color,
      pointBackgroundColor: color,
    }
    if (_rssi === null) {
      _rssi = new Chart(ctx, {
        type: 'line',
        data: {datasets: []},
        options: {
          legend: {display: false, },
          tooltips: {enabled: false, },
          animation: { duration: 0 },
          scales: {
            xAxes: [{
              ticks: {fontColor: '#000', padding: 5, fontSize: 12},
              gridLines: { zeroLineColor: '#000', color: '#ccc', tickMarkLength: 5},
              type: 'time',
              time: {
                unit: 'hour',
                stepSize: 1,
                displayFormats: { hour: 'HH[h]', },
              }
            }],
          },
        },
      });
    }
    _rssi.data.datasets = [points];
    _rssi.options.scales.xAxes[0].time.min = _firstseen;
    _rssi.options.scales.xAxes[0].time.max = _lastseen;
    _rssi.update();
    $('#myModal').modal('handleUpdate');
  }

  function updateRSSIModal(d) {
    // reset mouse cursor to default
    $('html,body').css('cursor','default');
    // collapse possible collapsed toggle
    $('#collapseLog').collapse('hide');

    var mac = d.label;
    $('#myModal').modal('show');
    // don't do any calculation if the data are already there
    if (mac == _mac) {
      return true;
    }
    _mac = mac;
    $('#mac').text(mac).css('color', d.pointBorderColor);
    $('#vendor').text(d.vendor);
    // stats
    var pr = d.data;
    var min = 100, max = -100, avg = 0, rssis = [], html = '';
    $('#mac_probes').empty();
    var count = 0;
    for (let p of pr) {
      min = Math.min(min, p.rssi);
      max = Math.max(max, p.rssi);
      avg += p.rssi;
      rssis.push(p.rssi);
      // logs
      if (count != 0 && count % 100 == 0) {
        var start = count - 100;
        var end = count -1;
        html += '<tr><td colspan="3"><a href="#" class="link-data" data-range="'+start+'-'+end+'">'+'Click to see range '+start+'-'+end+'</a></td></tr>';
      }
      count += 1;
    }
    count -= 1;
    if (count % 100 > -1) {
      var start = count - (count % 100);
      var end = count;
      html += '<tr><td colspan="3"><a href="#" class="link-data" data-range="'+start+'-'+end+'">'+'Click to see range '+start+'-'+end+'</a></td></tr>';
    }
    var ssids = [...d.ssids];
    if (ssids.indexOf('') > -1) {
      ssids.splice(ssids.indexOf(''), 1);
    }
    $('#ssids').text(ssids.join(', ')||'<none>');
    $('#count').text(pr.length);
    $('#min').text(min);
    $('#max').text(max);
    $('#avg').text((avg/pr.length).toFixed(1));
    $('#mdn').text(median(rssis));
    $('#mac_probes').html(html);
    // rssi chart
    drawRSSIChart(pr, d.pointBorderColor);
    // add link behavior and display more data
    $('.link-data').off('click');
    $('.link-data').on('click', function(e) {
      e.preventDefault();
      var range = $(this).data('range'), [start, end] = range.split('-');
      var html = '', indx;
      for (let i=0; i<_ds.length; i++) {
        if (_ds[i].label == _mac) {
          indx = i;
          break;
        }
      }
      for (let i=parseInt(start); i<=parseInt(end); i++) {
        var p = _ds[indx].data[i];
        html += '<tr><td class="ts">'+moment(p.x).format('YYYY-MM-DD HH:mm:ss')+'</td><td class="rssi">'+p.rssi+'</td><td>'+(d.ssids[p.ssid]||'&lt;empty&gt;')+'</td></tr>';
      }
      $(this).parents('tr').first().replaceWith(html);
    });
  }

  function drawMainChart(ctx, ds) {
    _chart = new Chart(ctx, {
      type: 'line',
      backgroundColor: '#ffffff',
      data: { datasets: ds, },
      options: {
        tooltips: {displayColors: false, titleFontFamily: 'monospace', intersect: false,
          callbacks: {
            title: function(tooltip, data) {
              var dsi = Array.isArray(tooltip) ? tooltip[0].datasetIndex : tooltip.datasetIndex;
              var t = data.datasets[dsi].label;
              var v = data.datasets[dsi].vendor;
              return t+'\n'+v;
            },
            label: function(tooltip, data) {
              var t = Array.isArray(tooltip) ? tooltip[0] : tooltip;
              var d = data.datasets[t.datasetIndex];
              var l = moment(d.data[t.index].x).format('YYYY-MM-DD HH:mm:ss');
              var r = d.data[t.index].rssi;
              var s = d.ssids[d.data[t.index].ssid] || '<empty>';
              return l+' / '+r+' / '+s;
            },
          }
        },
        responsive: true,
        animation: { duration: 0 },
        legend: {display: true, position: 'left',
          labels: {boxWidth: 25, fontSize: 12, fontFamily: 'monospace', fontColor: '#000',},
          onClick: function(e, item) {
            updateRSSIModal(_ds[item.datasetIndex]);
          },
          onHover: function(e, item) {
            $('html,body').css('cursor','pointer');
          },
          onLeave: function(e, item) {
            $('html,body').css('cursor','default');
          }
        },
        scales: {
          xAxes: [{
            ticks: {fontColor: '#000', padding: 5, fontSize: 12},
            gridLines: { zeroLineColor: '#000', color: '#ccc', tickMarkLength: 5},
            type: 'time',
            time: {
              unit: 'hour',
              stepSize: 1,
              displayFormats: { hour: 'HH[h]', }
            }
          }, {
            position: 'top',
            ticks: { display: false },
            gridLines: {zeroLineColor: '#000'}
          }],
          yAxes: [{
            ticks: { display: false, min: -1, max: ds.length },
            gridLines: { display: false, drawTicks: false, zeroLineColor: '#000' }
          }, {
            position: 'right',
            ticks: { display: false },
            gridLines: { display: false, drawTicks: false, zeroLineColor: '#000' }
          }],
        }
      }
    });
  }

  function updateMainChart(chart, ds) {
    chart.data.datasets = ds;
    chart.options.scales.yAxes[0].ticks.max = ds.length;
    chart.update();
  }

  function refresh(chart, date, after, before) {
    // don't do anything if the modal is opened
    if (($("#myModal").data('bs.modal') || {})._isShown) {
      return false;
    }
    updateDBTime();
    $('#loading').show();
    _mac = null; // to force update of modal data
    $('#msg').finish().addClass('alert-info').removeClass('alert-danger').show();
    // disable temporarly the datepicker
    $('#dp').datepicker('setStartDate', date).datepicker('setEndDate', date).datepicker('update', date);
    // disable refresh button
    $('#refresh').attr('disabled', 'disabled');

    var url;
    if (typeof after == 'undefined' || typeof before == 'undefined') {
      url = '/api/probes?today=true';
      _firstseen = moment().subtract(1, 'days').valueOf();
      _lastseen = moment().valueOf();
    } else {
      url = '/api/probes?after='+after+'&before='+before;
      _firstseen = moment(after).valueOf()
      _lastseen = moment(before).valueOf();
    }
    $.ajax({
      url: url,
      dataType: 'json',
    }).done(function(data) {
      if (data.length == 0) {
        $('#msg').removeClass('alert-info').addClass('alert-danger').text('No data found');
        $('#msg').fadeOut(5000, function() { $('#msg').text('Downloading data...'); });
        $('#loading').hide();
        return false;
      }
      $('#msg').hide();
      $('#loading').hide();
      _ds = repack(data);
      if ($('#myChart').is(':visible')) {
       // don't show the chart on mobile
       if (chart === null) {
         drawMainChart(ctx, _ds);
       } else {
         updateMainChart(chart, _ds);
       }
      } else {
        // but use a table for mobile
        var macs = '', c = 0, color;
        var gen = colorGenerator();
        for (let d of data) {
          if (d.known) {
            color = '#d62728';
          } else if (d.mac == 'LAA') {
            color = '#7f7f7f';
          } else {
            color = gen.next().value;
          }
          var min = 100, max= -100, avg = 0, rssis = [];
          for (let p of d.probereq) {
            min = Math.min(min, p.rssi);
            max = Math.max(max, p.rssi);
            avg += p.rssi;
            rssis.push(p.rssi);
          }
          var ssids = [...d.ssids];
          if (ssids.indexOf('') > -1) {
            ssids.splice(ssids.indexOf(''), 1);
          }
          macs += '<tr class="small-mono mac-stats"><td style="background-color:'+color+'"></td>';
          macs += '<td>'+d.mac+'</td>';
          macs += '<td>'+d.probereq.length+'</td>';
          macs += '<td>'+min+'</td>';
          macs += '<td>'+max+'</td>';
          macs += '<td>'+(avg/d.probereq.length).toFixed(1)+'</td>';
          macs += '<td>'+median(rssis)+'</td>';
          macs += '<td class="ts">'+moment(d.probereq[0].ts).format('HH:mm:ss')+'</td>';
          macs += '<td class="ts">'+moment(d.probereq[d.probereq.length-1].ts).format('HH:mm:ss')+'</td>';
          macs += '<td>'+(ssids.join(', ')||'&lt;none&gt;')+'</td></tr>';
        }
        $('#macs').html(macs);
        // but use the same modal
        $('.mac-stats').click(function(e) {
          e.preventDefault();
          $('#myModal').show();
          var mac = $(this).children('td').eq(1).text();
          var indx = 0;
          for (let d of _ds) {
            if (d.label == mac) {
              break;
            }
            indx += 1;
          }
          updateRSSIModal(_ds[indx]);
        });
      }
    }).fail(function(jq, status, error){
      $('#loading').hide();
      $('#msg').removeClass('alert-info').addClass('alert-danger').text('An error occured when downloading data');
      $('#msg').fadeOut(500, function() { $('#msg').text('Downloading data...'); });
    }).always(function() {
      // restore datepicker back to original state
      $('#dp').datepicker('setStartDate', false).datepicker('setEndDate', today).datepicker('update', date);
      $('#refresh').removeAttr('disabled');
    });
  }

  // draw initial message on canvas
  var ctx = document.getElementById('myChart').getContext('2d');
  ctx.width = $('#myChart').width();
  ctx.height = $('#myChart').height();
  var dx = ctx.width/2;
  var dy = ctx.height/2;
  ctx.font = '30px sans-serif';
  ctx.fillStyle = 'grey';
  ctx.textAlign = 'center';
  ctx.fillText('Please wait...', dx, dy-30);
  ctx.fillText('while chart.js is rendering your chart.', dx, dy);

  // datepicker code
  var today = moment().format('YYYY-MM-DD');
  var dp_options = {container: '#dp', weekStart: 1, format: 'yyyy-mm-dd', endDate: today};
  $('#dp').datepicker(dp_options).on('changeDate', function (e) {
    // load data for the picked date
    var date = moment(e.date).format('YYYY-MM-DD');
    var after = date+'T00:00:00';
    var before = date+'T23:59:59';
    refresh(_chart, date, after, before);
    //
  });
  $('#dp').datepicker('update', today);

  $('#refresh').click(function() {
    var now = moment().format('YYYY-MM-DD');
    if (now > today) {
      today = now;
    }
    refresh(_chart, today);
  });

  $('#refresh').trigger('click');

  // refresh chart when window is visible again
  $(document).on('visibilitychange', function() {
    if (document.visibilityState == "visible") {
      var chosen_date = moment($('#dp').datepicker('getDate')).format('YYYY-MM-DD');
      if (chosen_date == today) {
        $('#refresh').trigger('click');
      }
    }
  });

  // code to sort table on header click (from https://stackoverflow.com/a/49041392/283067)
  const getCellValue = (tr, idx) => tr.children[idx].innerText || tr.children[idx].textContent;

  const comparer = (idx, asc) => (a, b) => ((v1, v2) =>
    v1 !== '' && v2 !== '' && !isNaN(v1) && !isNaN(v2) ? v1 - v2 : v1.toString().localeCompare(v2)
    )(getCellValue(asc ? a : b, idx), getCellValue(asc ? b : a, idx));

  document.querySelectorAll('th.sortable').forEach(th => th.addEventListener('click', (() => {
    const tbody = document.querySelector('#macs');
    Array.from(tbody.querySelectorAll('tr:nth-child(n)'))
      .sort(comparer(Array.from(th.parentNode.children).indexOf(th), this.asc = !this.asc))
      .forEach(tr => tbody.appendChild(tr) );
  })));
})
