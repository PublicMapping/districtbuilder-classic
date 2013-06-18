
/* DistrictBuilder Javascript Utilities */

/* DistrictBuilder Javascript Utilities used in multiple
 * Javascript files in the DistrictBuilder codebase.
 * 
 * Instantiate DB object to protect global namespace
 */

var DB = {};
DB.util = {};

/* Checks whether a string starts with a substring 
 *
 * Parameters:
 *   s -- string to compare
 *   substring -- characters to check if s starts with
 */

DB.util.startsWith = function(s, substring) {
    return (s.indexOf(substring) == 0);
}

/* Checks whether a string contains a given substring 
 *
 * Parameters:
 *   s -- string to compare
 *   substring -- characters to check if s contains
 */

DB.util.contains = function(s, substring) {
    return (s.indexOf(substring) != -1);
};
