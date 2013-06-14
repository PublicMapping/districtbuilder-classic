
/* DistrictBuilder Javascript Utilities */

/* DistrictBuilder Javascript Utilities used in multiple
 * Javascript files in the DistrictBuilder codebase.
 * 
 * Instantiate db_util object to protect global namespace
 */

var db_util = {};

/* Checks whether a string starts with a substring 
 *
 * Parameters:
 *   s -- string to compare
 *   substring -- characters to check if s starts with
 */

db_util.startsWith = function(s, substring) {
    return (s.indexOf(substring) == 0);
}

/* Checks whether a string contains a given substring 
 *
 * Parameters:
 *   s -- string to compare
 *   substring -- characters to check if s contains
 */

db_util.contains = function(s, substring) {
    return (s.indexOf(substring) != -1);
};
