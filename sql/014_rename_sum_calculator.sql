UPDATE publicmapping.redistricting_scorefunction 
   SET calculator = 'publicmapping.redistricting.calculators.SumValues'
 WHERE calculator = 'publicmapping.redistricting.calculators.Sum';
