# -*- coding: utf-8 -*-
"""
IsoFlux MS-XLS Report Module

Ulrich Lukas 2017-06-16
"""
from datetime import datetime
import json
import xlsxwriter

### Configuration: #############
TITLE = "IsoFlux Messdatenreport"
REPORT_SHEET_NAME = "Messdatenprotokoll"
CHART_SHEET_NAME = "Messung.{index:02d}"
TIME_PREFIX = "Messung vom: "
REPORT_ROW_OFST = 4
CHART_ROW_OFST = 41
STEP = 5
################################

# Read report data from IsoFlux JSON export
with open("ifx1.report") as f:
    inp_report = json.loads(f.read())
##inp_report = json.loads(msg["payload"])
#%%


# Create new Excel file:
# wb = xlsxwriter.Workbook(TITLE + " {}.xlsx".format(start_string))
wb = xlsxwriter.Workbook("/tmp/ifx1.xlsx")

# Define some cell formats:
bold_16pt = wb.add_format({
    "bold": True, "font_color": "blue", "font_size": 16, "align": "left"
})
bold_centered = wb.add_format({
    "bold": True, "align": "center", "valign": "vcenter", "text_wrap": True
})
comment_format = wb.add_format({
    "bold": True, "font_color": "green", "align": "left"
})
number_format = wb.add_format({"num_format": "0.0"})
date_format = wb.add_format({
    "align": "left", "num_format": "yyyy-mm-dd  hh:mm"
})

# Create first worksheet inside that file:
ws_1 = wb.add_worksheet(REPORT_SHEET_NAME)

# Write report summary with comments to the first worksheet
ws_1.write(0, 0, TITLE, bold_16pt)
ws_1.set_row(0, height=20)
#%%
for index, record in enumerate(inp_report):
    # Write to log records to report summary on first worksheet:
    row = REPORT_ROW_OFST + index*STEP
    record_timestamp = datetime.fromtimestamp(record["timestamp"])
    chart_name = CHART_SHEET_NAME.format(index=index)
    
    ws_1.merge_range(row, 0, row, 1, "")
    ws_1.write_datetime(row, 0, record_timestamp, date_format)
    ws_1.merge_range(row, 2, row, 3, record["author"])
    ws_1.merge_range(row, 4, row, 5, "Diagramm:".format(chart_name))
    ws_1.write(row, 6, "internal:'{}'!A1".format(chart_name))
    ws_1.write(row+1, 0, record["comment"], comment_format)
    labels = ["{}\n/W".format(i) for i in record["labels"]]
    for i, label in enumerate(record["labels"]):
        ws_1.write(row+2, i, "{}\n/W".format(label), bold_centered)
        ws_1.set_column(i, i, width=len(label)+1)
    ws_1.set_row(row+2, height=30)

    ws_1.write_row(row+3, 0, record["power"], number_format)
    
    
    # Write record chart on a new individual worksheet:
    ws_n = wb.add_worksheet(chart_name)
    inp_chart = record["chart"]

    data_titles = [i["key"] for i in inp_chart]
    table_titles = ["Zeit\n/s"] + [i+"\n/W" for i in data_titles]

    start_msec = inp_chart[0]["values"][0][0]
    timescale = [int((i[0] - start_msec)/1000) for i in inp_chart[0]["values"]]
    n_data_rows = len(timescale)
    data_columns = [[j[1] for j in i["values"]] for i in inp_chart]
    n_data_cols = len(data_columns)

    ws_n.write(0, 0, TITLE, bold_16pt)
    ws_n.set_row(0, height=20)
    ws_n.merge_range(1, 0, 1, 1, TIME_PREFIX)
    ws_n.merge_range(1, 2, 1, 3, record_timestamp, date_format)
    # Row A5... is data column titles:
    row = CHART_ROW_OFST
    ws_n.write_row(row, 0, table_titles, bold_centered)
    ws_n.set_row(row, height=30)
    # Column A6... is time:
    ws_n.write_column(row+1, 0, timescale)
    # Columns B6... is data:
    for i, column in enumerate(data_columns, start=1):
        ws_n.write_column(row+1, i, column, number_format)
        ws_n.set_column(i, i, width=len(data_titles[i-1])+1)

    # Create a new chart object:
    chart = wb.add_chart({"type": "scatter", "subtype": "straight"})
    chart.set_size({"width": 1024, "height": 768})
    chart.set_legend({'position': 'top'})

    # Add data series to the chart, defining references
    # to cell ranges containing the respective data:
    for i in range(1, n_data_cols+1):
        chart.add_series({
            "name": [chart_name, row, i],
            "categories": [chart_name, row+1, 0, row+n_data_rows, 0],
            "values": [chart_name, row+1, i, row+n_data_rows, i],
        })

    # Add the chart object to the second worksheet:
    ws_n.insert_chart("A3", chart)
#%%
# Close workbook, writing file to disk:
wb.close()

#return {"topic": "download_ready"}