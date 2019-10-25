def convertSecondsToHMFS(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    return "%d:%02d:%02d" % (hour, minutes, seconds)

# Move an table item up (+1) or down (-1)
def moveTableRow(control, directionValue):
    rowCount = control.rowCount()
    colCount = control.columnCount()
    rowIndex = control.currentRow()
    if rowIndex + directionValue >= 0 and rowIndex + directionValue <= rowCount - 1:
        for colIndex in range(colCount):
            item = control.takeItem(rowIndex, colIndex)
            prevItem = control.takeItem(rowIndex + directionValue, colIndex)
            control.setItem(rowIndex, colIndex, prevItem)
            control.setItem(rowIndex + directionValue, colIndex, item)
        control.setCurrentItem(item)
